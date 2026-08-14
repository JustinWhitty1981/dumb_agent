package agent

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"jada-backend/pkg/formatters"
	"jada-backend/pkg/llm"
	"jada-backend/pkg/tools"
)

const SystemPrompt = `You are J.A.D.A, an enterprise AI assistant with access to web search, web scraping, memory storage, and industrial HighByte MCP tools. You maintain context across multiple turns.

Available default tools:
- current_time(): Get current date and time in both UTC (ISO-8601) and local timezone.
- search_web(query): Search the web using Tavily API.
- scrape_url(url): Scrape text content from a web URL.
- save_memory_tool(key, content), get_memory_tool(key), list_memories_tool(): Persistent memory storage.

CRITICAL REQUIREMENT FOR HIGHBYTE MCP TOOLS (e.g., paint_defects, influx_query_router, workorder_tracker_v1):
1. When querying HighByte tools for recent data, ALWAYS check current time first using current_time().
2. HighByte timestamp parameters (start_ts, end_ts) MUST ALWAYS be provided as UTC ISO-8601 strings in the format YYYY-MM-DDTHH:MM:SSZ (e.g. '2026-08-12T00:00:00Z').
3. When calling InsightsPublish, set agent_name = 'J.A.D.A'.
4. Always analyze tool results and present a human-readable summary in Markdown (bold headers, key metrics, summary bullet points). Never output raw JSON arrays directly as your response.`

const MaxHistoryMessages = 10

type ChatMessage struct {
	Role       string     `json:"role"`
	Content    string     `json:"content,omitempty"`
	Name       string     `json:"name,omitempty"`
	ToolCallID string     `json:"tool_call_id,omitempty"`
	ToolCalls  []ToolCall `json:"tool_calls,omitempty"`
}

type ToolCall struct {
	ID       string       `json:"id"`
	Type     string       `json:"type"`
	Function ToolFunction `json:"function"`
}

type ToolFunction struct {
	Name      string `json:"name"`
	Arguments string `json:"arguments"`
}

type OpenAITool struct {
	Type     string             `json:"type"`
	Function OpenAIToolFunction `json:"function"`
}

type OpenAIToolFunction struct {
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Parameters  map[string]interface{} `json:"parameters"`
}

type ChatCompletionRequest struct {
	Model       string        `json:"model"`
	Messages    []ChatMessage `json:"messages"`
	Tools       []OpenAITool  `json:"tools,omitempty"`
	Temperature float64       `json:"temperature"`
	Stream      bool          `json:"stream"`
}

// Chunk structures for vLLM streaming responses
type StreamDelta struct {
	Role      string           `json:"role,omitempty"`
	Content   string           `json:"content,omitempty"`
	ToolCalls []StreamToolCall `json:"tool_calls,omitempty"`
}

type StreamToolCall struct {
	Index    int                `json:"index"`
	ID       string             `json:"id,omitempty"`
	Type     string             `json:"type,omitempty"`
	Function StreamToolFunction `json:"function"`
}

type StreamToolFunction struct {
	Name      string `json:"name,omitempty"`
	Arguments string `json:"arguments,omitempty"`
}

type ChatCompletionChunkChoice struct {
	Index        int         `json:"index"`
	Delta        StreamDelta `json:"delta"`
	FinishReason string      `json:"finish_reason,omitempty"`
}

type ChatCompletionChunk struct {
	ID      string                      `json:"id"`
	Choices []ChatCompletionChunkChoice `json:"choices"`
}

type AgentManager struct {
	LLMProvider  string
	VLLMURL      string
	VLLMModel    string
	TokenProv    *llm.TokenProvider
	Tools        map[string]tools.ToolDefinition
	ToolList     []tools.ToolDefinition
	History      map[string][]ChatMessage
	historyMutex sync.RWMutex
}

func NewAgentManager(toolsList []tools.ToolDefinition) *AgentManager {
	llmProvider := strings.ToLower(os.Getenv("LLM_PROVIDER"))
	if llmProvider == "azure" || llmProvider == "azure_gcc_high" {
		llmProvider = "azure_gcc_high"
	} else {
		llmProvider = "local"
	}

	vllmURL := os.Getenv("VLLM_BASE_URL")
	if vllmURL == "" {
		vllmURL = "http://172.18.0.2:8000/v1"
	}
	vllmModel := os.Getenv("VLLM_MODEL")
	if vllmModel == "" {
		vllmModel = "/models/Qwen3.5-9B-AWQ"
	}

	toolMap := make(map[string]tools.ToolDefinition)
	for _, t := range toolsList {
		toolMap[t.Name] = t
	}

	am := &AgentManager{
		LLMProvider: llmProvider,
		VLLMURL:     vllmURL,
		VLLMModel:   vllmModel,
		Tools:       toolMap,
		ToolList:    toolsList,
		History:     make(map[string][]ChatMessage),
	}

	if llmProvider == "azure_gcc_high" {
		am.TokenProv = llm.NewAzureTokenProvider()
	}

	return am
}

func (am *AgentManager) GetHistory(threadID string) []ChatMessage {
	am.historyMutex.RLock()
	defer am.historyMutex.RUnlock()

	hist := am.History[threadID]
	copied := make([]ChatMessage, len(hist))
	copy(copied, hist)
	return copied
}

func (am *AgentManager) ResetHistory(threadID string) {
	am.historyMutex.Lock()
	defer am.historyMutex.Unlock()
	delete(am.History, threadID)
}

func (am *AgentManager) updateHistory(threadID string, userMsg, assistantMsg string) {
	am.historyMutex.Lock()
	defer am.historyMutex.Unlock()

	hist := am.History[threadID]
	hist = append(hist, ChatMessage{Role: "user", Content: userMsg})
	hist = append(hist, ChatMessage{Role: "assistant", Content: assistantMsg})

	if len(hist) > MaxHistoryMessages {
		hist = hist[len(hist)-MaxHistoryMessages:]
	}
	am.History[threadID] = hist
}

func (am *AgentManager) getOpenAITools() []OpenAITool {
	var openAITools []OpenAITool
	for _, t := range am.ToolList {
		openAITools = append(openAITools, OpenAITool{
			Type: "function",
			Function: OpenAIToolFunction{
				Name:        t.Name,
				Description: t.Description,
				Parameters:  t.Parameters,
			},
		})
	}
	return openAITools
}

type SSEEvent struct {
	Type    string `json:"type"`
	Content string `json:"content,omitempty"`
}

type toolCallAcc struct {
	ID        string
	Type      string
	Name      string
	Arguments strings.Builder
}

func (am *AgentManager) RunChatStream(threadID, userMessage string, eventChan chan<- SSEEvent) {
	defer close(eventChan)

	if strings.TrimSpace(strings.ToLower(userMessage)) == "/reset" {
		am.ResetHistory(threadID)
		eventChan <- SSEEvent{Type: "token", Content: "Conversation history reset."}
		eventChan <- SSEEvent{Type: "done"}
		return
	}

	history := am.GetHistory(threadID)

	var messages []ChatMessage
	messages = append(messages, ChatMessage{Role: "system", Content: SystemPrompt})
	messages = append(messages, history...)
	messages = append(messages, ChatMessage{Role: "user", Content: userMessage})

	openAITools := am.getOpenAITools()

	var endpoint string
	var modelName string
	if am.LLMProvider == "azure_gcc_high" {
		endpoint, modelName = llm.GetAzureConfig()
	} else {
		endpoint = fmt.Sprintf("%s/chat/completions", strings.TrimSuffix(am.VLLMURL, "/"))
		modelName = am.VLLMModel
	}

	client := &http.Client{Timeout: 120 * time.Second}
	var fullAssistantResponse []string
	var lastToolOutput string

	for iteration := 0; iteration < 10; iteration++ {
		eventChan <- SSEEvent{Type: "status", Content: "Thinking..."}

		reqPayload := ChatCompletionRequest{
			Model:       modelName,
			Messages:    messages,
			Tools:       openAITools,
			Temperature: 0.0,
			Stream:      true, // Enable real-time token streaming
		}

		jsonBytes, err := json.Marshal(reqPayload)
		if err != nil {
			eventChan <- SSEEvent{Type: "error", Content: fmt.Sprintf("Failed to marshal LLM request: %v", err)}
			eventChan <- SSEEvent{Type: "done"}
			return
		}

		httpReq, err := http.NewRequest("POST", endpoint, bytes.NewBuffer(jsonBytes))
		if err != nil {
			eventChan <- SSEEvent{Type: "error", Content: fmt.Sprintf("Failed to create HTTP request: %v", err)}
			eventChan <- SSEEvent{Type: "done"}
			return
		}
		httpReq.Header.Set("Content-Type", "application/json")
		httpReq.Header.Set("Accept", "text/event-stream")

		if am.LLMProvider == "azure_gcc_high" {
			apiKey := strings.TrimSpace(os.Getenv("AZURE_OPENAI_API_KEY"))
			if apiKey != "" {
				httpReq.Header.Set("api-key", apiKey)
				httpReq.Header.Set("Authorization", fmt.Sprintf("Bearer %s", apiKey))
			} else if am.TokenProv != nil {
				token, err := am.TokenProv.GetBearerToken()
				if err != nil {
					eventChan <- SSEEvent{Type: "error", Content: fmt.Sprintf("Failed to acquire Azure OAuth token: %v", err)}
					eventChan <- SSEEvent{Type: "done"}
					return
				}
				httpReq.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))
			}
		}

		resp, err := client.Do(httpReq)
		if err != nil {
			eventChan <- SSEEvent{Type: "error", Content: fmt.Sprintf("Error connecting to LLM server (%s): %v", am.LLMProvider, err)}
			eventChan <- SSEEvent{Type: "done"}
			return
		}

		// Handle 401 retry once if using Azure
		if resp.StatusCode == http.StatusUnauthorized && am.LLMProvider == "azure_gcc_high" && am.TokenProv != nil {
			resp.Body.Close()
			am.TokenProv.Invalidate()
			token, err := am.TokenProv.GetBearerToken()
			if err == nil {
				retryReq, _ := http.NewRequest("POST", endpoint, bytes.NewBuffer(jsonBytes))
				retryReq.Header.Set("Content-Type", "application/json")
				retryReq.Header.Set("Accept", "text/event-stream")
				retryReq.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))
				resp, err = client.Do(retryReq)
			}
		}

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			eventChan <- SSEEvent{Type: "error", Content: fmt.Sprintf("LLM API error status %d: %s", resp.StatusCode, string(body))}
			eventChan <- SSEEvent{Type: "done"}
			return
		}

		reader := bufio.NewReader(resp.Body)
		var turnTextBuilder strings.Builder
		toolAccMap := make(map[int]*toolCallAcc)

		for {
			line, err := reader.ReadString('\n')
			if err != nil {
				break
			}

			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, ":") {
				continue
			}

			if !strings.HasPrefix(line, "data:") {
				continue
			}

			dataStr := strings.TrimSpace(strings.TrimPrefix(line, "data:"))
			if dataStr == "[DONE]" {
				break
			}

			var chunk ChatCompletionChunk
			if err := json.Unmarshal([]byte(dataStr), &chunk); err != nil {
				continue
			}

			if len(chunk.Choices) == 0 {
				continue
			}

			choice := chunk.Choices[0]

			// Stream text tokens in real time to eventChan
			if choice.Delta.Content != "" {
				turnTextBuilder.WriteString(choice.Delta.Content)
				eventChan <- SSEEvent{Type: "token", Content: choice.Delta.Content}
			}

			// Accumulate streaming tool call deltas
			if len(choice.Delta.ToolCalls) > 0 {
				for _, stc := range choice.Delta.ToolCalls {
					idx := stc.Index
					acc, exists := toolAccMap[idx]
					if !exists {
						acc = &toolCallAcc{}
						toolAccMap[idx] = acc
					}

					if stc.ID != "" {
						acc.ID = stc.ID
					}
					if stc.Type != "" {
						acc.Type = stc.Type
					}
					if stc.Function.Name != "" {
						acc.Name = stc.Function.Name
					}
					if stc.Function.Arguments != "" {
						acc.Arguments.WriteString(stc.Function.Arguments)
					}
				}
			}
		}
		resp.Body.Close()

		turnText := turnTextBuilder.String()
		if turnText != "" {
			fullAssistantResponse = append(fullAssistantResponse, turnText)
		}

		var toolCalls []ToolCall
		for i := 0; i < len(toolAccMap); i++ {
			if acc, ok := toolAccMap[i]; ok {
				toolCalls = append(toolCalls, ToolCall{
					ID:   acc.ID,
					Type: acc.Type,
					Function: ToolFunction{
						Name:      acc.Name,
						Arguments: acc.Arguments.String(),
					},
				})
			}
		}

		assistantMsg := ChatMessage{
			Role:      "assistant",
			Content:   turnText,
			ToolCalls: toolCalls,
		}

		messages = append(messages, assistantMsg)

		// If no tool calls were generated by LLM, turn loop completes
		if len(toolCalls) == 0 {
			break
		}

		// Execute tool calls
		for _, tc := range toolCalls {
			toolName := tc.Function.Name
			eventChan <- SSEEvent{Type: "status", Content: fmt.Sprintf("Running tool: %s...", toolName)}

			var argsMap map[string]interface{}
			if tc.Function.Arguments != "" {
				_ = json.Unmarshal([]byte(tc.Function.Arguments), &argsMap)
			}
			if argsMap == nil {
				argsMap = make(map[string]interface{})
			}

			var toolOutput string
			if tDef, exists := am.Tools[toolName]; exists {
				strictPolicies := strings.ToLower(os.Getenv("STRICT_TOOL_POLICIES"))
				isStrict := strictPolicies == "true" || strictPolicies == "1" || strictPolicies == "yes"

				hitlEnv := strings.ToLower(os.Getenv("INSIGHT_HUMAN_IN_THE_LOOP"))
				isInsightPublish := strings.Contains(strings.ToLower(toolName), "insightspublish") || strings.Contains(strings.ToLower(toolName), "publish")
				isHITL := isInsightPublish && (hitlEnv == "true" || hitlEnv == "1" || hitlEnv == "yes")

				approved, _ := argsMap["approved"].(bool)

				if (isHITL || (isStrict && tDef.Policy.RequiresApproval)) && !approved {
					toolOutput = fmt.Sprintf("Tool execution blocked: Tool '%s' requires human-in-the-loop approval before execution. Set INSIGHT_HUMAN_IN_THE_LOOP=false or STRICT_TOOL_POLICIES=false to bypass.", toolName)
				} else {
					out, err := tDef.Execute(argsMap)
					if err != nil {
						toolOutput = fmt.Sprintf("Error executing tool '%s': %v", toolName, err)
					} else {
						toolOutput = out
					}
				}
			} else {
				toolOutput = fmt.Sprintf("Error: tool '%s' not found.", toolName)
			}

			lastToolOutput = toolOutput
			eventChan <- SSEEvent{Type: "status", Content: fmt.Sprintf("Finished %s, reasoning...", toolName)}

			messages = append(messages, ChatMessage{
				Role:       "tool",
				Name:       toolName,
				ToolCallID: tc.ID,
				Content:    toolOutput,
			})
		}
	}

	finalText := strings.TrimSpace(strings.Join(fullAssistantResponse, ""))
	if finalText == "" {
		fallback := formatters.FormatFallbackToolSummary(lastToolOutput)
		eventChan <- SSEEvent{Type: "token", Content: fallback}
		finalText = fallback
	}

	am.updateHistory(threadID, userMessage, finalText)
	eventChan <- SSEEvent{Type: "done"}
}

func (am *AgentManager) RunChatSync(threadID, userMessage string) (string, error) {
	if strings.TrimSpace(strings.ToLower(userMessage)) == "/reset" {
		am.ResetHistory(threadID)
		return "Conversation history has been reset.", nil
	}

	eventChan := make(chan SSEEvent, 100)
	go am.RunChatStream(threadID, userMessage, eventChan)

	var tokens []string
	for ev := range eventChan {
		if ev.Type == "token" {
			tokens = append(tokens, ev.Content)
		} else if ev.Type == "error" {
			return "", fmt.Errorf("%s", ev.Content)
		}
	}

	out := strings.Join(tokens, "")
	if out == "" {
		out = "Task completed successfully."
	}
	return out, nil
}
