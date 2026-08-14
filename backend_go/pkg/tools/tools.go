package tools

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"jada-backend/pkg/memory"

	"github.com/PuerkitoBio/goquery"
)

type ToolDefinition struct {
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Parameters  map[string]interface{} `json:"parameters"`
	Execute     func(args map[string]interface{}) (string, error)
}

func GetCurrentTime() (string, error) {
	nowUTC := time.Now().UTC()
	nowLocal := time.Now()
	tzName := os.Getenv("TZ")
	if tzName == "" {
		tzName = "America/Chicago"
	}

	return fmt.Sprintf(
		"Current UTC time (for UTC ISO parameters): %s\nCurrent Local time (%s): %s",
		nowUTC.Format("2006-01-02T15:04:05Z"),
		tzName,
		nowLocal.Format("2006-01-02 15:04:05"),
	), nil
}

type TavilySearchRequest struct {
	Query       string `json:"query"`
	SearchDepth string `json:"search_depth"`
	MaxResults  int    `json:"max_results"`
}

type TavilySearchResult struct {
	Title   string `json:"title"`
	Content string `json:"content"`
	URL     string `json:"url"`
}

type TavilyResponse struct {
	Results []TavilySearchResult `json:"results"`
}

func SearchWeb(query string) (string, error) {
	apiKey := os.Getenv("TAVILY_API_KEY")
	if apiKey == "" {
		return "Tavily API key not configured. Please set TAVILY_API_KEY environment variable.", nil
	}

	reqBody := TavilySearchRequest{
		Query:       query,
		SearchDepth: "basic",
		MaxResults:  5,
	}

	jsonBytes, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("failed to marshal tavily request: %w", err)
	}

	req, err := http.NewRequest("POST", "https://api.tavily.com/search", bytes.NewBuffer(jsonBytes))
	if err != nil {
		return "", fmt.Errorf("failed to create tavily request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", apiKey))

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Sprintf("Search failed: %v", err), nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Sprintf("Search failed with status %d: %s", resp.StatusCode, string(body)), nil
	}

	var tavilyResp TavilyResponse
	if err := json.NewDecoder(resp.Body).Decode(&tavilyResp); err != nil {
		return "", fmt.Errorf("failed to decode tavily response: %w", err)
	}

	if len(tavilyResp.Results) == 0 {
		return "No search results found.", nil
	}

	var formatted []string
	for i, res := range tavilyResp.Results {
		title := res.Title
		if title == "" {
			title = "No title"
		}
		snippet := res.Content
		if snippet == "" {
			snippet = "No description"
		}
		url := res.URL
		if url == "" {
			url = "No URL"
		}

		formatted = append(formatted, fmt.Sprintf("%d. **%s**\n   %s\n   URL: %s", i+1, title, snippet, url))
	}

	return strings.Join(formatted, "\n\n"), nil
}

func ScrapeURL(urlStr string) (string, error) {
	req, err := http.NewRequest("GET", urlStr, nil)
	if err != nil {
		return fmt.Sprintf("Failed to create request: %v", err), nil
	}

	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Sprintf("Failed to fetch URL: %v", err), nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Sprintf("Scraping failed with status: %d", resp.StatusCode), nil
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return fmt.Sprintf("Scraping failed: %v", err), nil
	}

	doc.Find("script, style, noscript").Each(func(i int, s *goquery.Selection) {
		s.Remove()
	})

	text := doc.Text()

	lines := strings.Split(text, "\n")
	var cleanedLines []string
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed != "" {
			cleanedLines = append(cleanedLines, trimmed)
		}
	}

	cleanedText := strings.Join(cleanedLines, "\n")

	if len(cleanedText) > 5000 {
		cleanedText = cleanedText[:5000] + "\n\n... (content truncated)"
	}

	return fmt.Sprintf("Content from %s:\n\n%s", urlStr, cleanedText), nil
}

func GetLocalTools() []ToolDefinition {
	return []ToolDefinition{
		{
			Name:        "current_time",
			Description: "Get the current date and time in both UTC (for ISO database queries) and local timezone.",
			Parameters: map[string]interface{}{
				"type":       "object",
				"properties": map[string]interface{}{},
			},
			Execute: func(args map[string]interface{}) (string, error) {
				return GetCurrentTime()
			},
		},
		{
			Name:        "search_web",
			Description: "Search the web using Tavily API.",
			Parameters: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"query": map[string]interface{}{
						"type":        "string",
						"description": "The search query string.",
					},
				},
				"required": []string{"query"},
			},
			Execute: func(args map[string]interface{}) (string, error) {
				q, _ := args["query"].(string)
				return SearchWeb(q)
			},
		},
		{
			Name:        "scrape_url",
			Description: "Scrape content from a web page URL.",
			Parameters: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"url": map[string]interface{}{
						"type":        "string",
						"description": "The URL to scrape.",
					},
				},
				"required": []string{"url"},
			},
			Execute: func(args map[string]interface{}) (string, error) {
				u, _ := args["url"].(string)
				return ScrapeURL(u)
			},
		},
		{
			Name:        "save_memory_tool",
			Description: "Save information to memory storage.",
			Parameters: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"key": map[string]interface{}{
						"type":        "string",
						"description": "A unique identifier for this memory.",
					},
					"content": map[string]interface{}{
						"type":        "string",
						"description": "The content to store.",
					},
				},
				"required": []string{"key", "content"},
			},
			Execute: func(args map[string]interface{}) (string, error) {
				key, _ := args["key"].(string)
				content, _ := args["content"].(string)
				return memory.SaveMemory(key, content), nil
			},
		},
		{
			Name:        "get_memory_tool",
			Description: "Retrieve stored information by key.",
			Parameters: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"key": map[string]interface{}{
						"type":        "string",
						"description": "The memory key to look up.",
					},
				},
				"required": []string{"key"},
			},
			Execute: func(args map[string]interface{}) (string, error) {
				key, _ := args["key"].(string)
				return memory.GetMemory(key), nil
			},
		},
		{
			Name:        "list_memories_tool",
			Description: "List all saved memory keys.",
			Parameters: map[string]interface{}{
				"type":       "object",
				"properties": map[string]interface{}{},
			},
			Execute: func(args map[string]interface{}) (string, error) {
				return memory.ListMemories(), nil
			},
		},
	}
}
