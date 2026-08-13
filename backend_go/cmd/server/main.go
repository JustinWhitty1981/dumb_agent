package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"

	"jada-backend/pkg/agent"
	"jada-backend/pkg/mcp"
	"jada-backend/pkg/tools"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
)

type ChatRequest struct {
	Message  string `json:"message"`
	ThreadID string `json:"thread_id,omitempty"`
}

type ChatResponse struct {
	Response string `json:"response"`
	ThreadID string `json:"thread_id"`
}

func main() {
	host := os.Getenv("HOST")
	if host == "" {
		host = "0.0.0.0"
	}
	portStr := os.Getenv("PORT")
	port := 8000
	if portStr != "" {
		if p, err := strconv.Atoi(portStr); err == nil {
			port = p
		}
	}

	localToolsList := tools.GetLocalTools()
	mcpToolsList := mcp.GetHighByteMCPTools()

	allTools := append(localToolsList, mcpToolsList...)
	agentMgr := agent.NewAgentManager(allTools)

	r := chi.NewRouter()

	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type"},
		AllowCredentials: true,
	}))

	r.Post("/api/chat", func(w http.ResponseWriter, r *http.Request) {
		var req ChatRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "Invalid JSON body", http.StatusBadRequest)
			return
		}

		threadID := req.ThreadID
		if threadID == "" {
			threadID = "default"
		}

		resStr, err := agentMgr.RunChatSync(threadID, req.Message)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(ChatResponse{
				Response: fmt.Sprintf("I encountered an error: %v. Reset thread context.", err),
				ThreadID: threadID,
			})
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(ChatResponse{
			Response: resStr,
			ThreadID: threadID,
		})
	})

	r.Post("/api/chat/stream", func(w http.ResponseWriter, r *http.Request) {
		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "Streaming unsupported!", http.StatusInternalServerError)
			return
		}

		var req ChatRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "Invalid JSON body", http.StatusBadRequest)
			return
		}

		threadID := req.ThreadID
		if threadID == "" {
			threadID = "default"
		}

		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")

		eventChan := make(chan agent.SSEEvent, 100)
		go agentMgr.RunChatStream(threadID, req.Message, eventChan)

		for ev := range eventChan {
			bytes, err := json.Marshal(ev)
			if err == nil {
				fmt.Fprintf(w, "data: %s\n\n", string(bytes))
				flusher.Flush()
			}
		}
	})

	r.Post("/api/reset", func(w http.ResponseWriter, r *http.Request) {
		threadID := r.URL.Query().Get("thread_id")
		if threadID == "" {
			threadID = "default"
		}
		agentMgr.ResetHistory(threadID)

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":  "success",
			"message": fmt.Sprintf("Conversation history reset for thread: %s", threadID),
		})
	})

	r.Get("/api/history", func(w http.ResponseWriter, r *http.Request) {
		threadID := r.URL.Query().Get("thread_id")
		if threadID == "" {
			threadID = "default"
		}

		hist := agentMgr.GetHistory(threadID)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"thread_id":     threadID,
			"history":       hist,
			"message_count": len(hist),
		})
	})

	r.Get("/api/tools", func(w http.ResponseWriter, r *http.Request) {
		var toolInfos []map[string]string
		for _, t := range agentMgr.ToolList {
			toolInfos = append(toolInfos, map[string]string{
				"name":        t.Name,
				"description": t.Description,
			})
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"total_tools": len(toolInfos),
			"tools":       toolInfos,
		})
	})

	r.Get("/api/health", func(w http.ResponseWriter, r *http.Request) {
		mcpURL := os.Getenv("HIGHBYTE_MCP_URL")
		if mcpURL == "" {
			mcpURL = "not-configured"
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":             "healthy",
			"vllm_url":           agentMgr.VLLMURL,
			"model":              agentMgr.VLLMModel,
			"active_tools_count": len(agentMgr.ToolList),
			"highbyte_mcp_url":   mcpURL,
		})
	})

	staticDir := "static"
	if _, err := os.Stat(staticDir); os.IsNotExist(err) {
		staticDir = "/app/backend_go/static"
	}

	if _, err := os.Stat(staticDir); err == nil {
		fileServer := http.FileServer(http.Dir(staticDir))
		r.Handle("/*", fileServer)
		r.Handle("/static/*", http.StripPrefix("/static/", fileServer))
	} else {
		r.Get("/", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]string{
				"message": "J.A.D.A Go API is running",
			})
		})
	}

	addr := fmt.Sprintf("%s:%d", host, port)
	log.Printf("Starting J.A.D.A Go Backend Server on %s", addr)
	if err := http.ListenAndServe(addr, r); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
