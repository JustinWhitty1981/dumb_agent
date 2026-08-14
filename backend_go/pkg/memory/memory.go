package memory

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

var (
	memoryMu  sync.RWMutex
	memoryDir = "memory_store"
)

func SetMemoryDir(dir string) {
	memoryMu.Lock()
	defer memoryMu.Unlock()
	memoryDir = dir
}

func EnsureMemoryDir() error {
	return os.MkdirAll(memoryDir, 0755)
}

func getMemoryFilePath(key string) string {
	re := regexp.MustCompile(`[^\w\-_\.]`)
	safeKey := re.ReplaceAllString(key, "_")
	return filepath.Join(memoryDir, fmt.Sprintf("%s.md", safeKey))
}

func SaveMemory(key, content string) string {
	memoryMu.Lock()
	defer memoryMu.Unlock()

	if err := EnsureMemoryDir(); err != nil {
		return fmt.Sprintf("Error creating memory directory: %v", err)
	}

	fp := getMemoryFilePath(key)
	timestamp := time.Now().Format("2006-01-02 15:04:05")

	entry := fmt.Sprintf("\n---\n**Timestamp:** %s\n**Content:**\n%s\n", timestamp, content)

	f, err := os.OpenFile(fp, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Sprintf("Error saving memory: %v", err)
	}
	defer f.Close()

	if _, err := f.WriteString(entry); err != nil {
		return fmt.Sprintf("Error writing memory: %v", err)
	}

	return fmt.Sprintf("Memory saved as: %s", key)
}

func GetMemory(key string) string {
	memoryMu.RLock()
	defer memoryMu.RUnlock()

	_ = EnsureMemoryDir()
	fp := getMemoryFilePath(key)

	data, err := os.ReadFile(fp)
	if err != nil {
		return fmt.Sprintf("No memory found with key '%s'", key)
	}

	return fmt.Sprintf("Memory for '%s':\n%s", key, string(data))
}

func ListMemories() string {
	memoryMu.RLock()
	defer memoryMu.RUnlock()

	_ = EnsureMemoryDir()

	entries, err := os.ReadDir(memoryDir)
	if err != nil || len(entries) == 0 {
		return "No memories stored yet."
	}

	var keys []string
	for _, entry := range entries {
		if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".md") {
			keys = append(keys, strings.TrimSuffix(entry.Name(), ".md"))
		}
	}

	if len(keys) == 0 {
		return "No memories stored yet."
	}

	sort.Strings(keys)
	var lines []string
	for _, k := range keys {
		lines = append(lines, fmt.Sprintf("- **%s**", k))
	}

	return fmt.Sprintf("Here are the currently stored memory keys:\n%s", strings.Join(lines, "\n"))
}

func DeleteMemory(key string) string {
	memoryMu.Lock()
	defer memoryMu.Unlock()

	_ = EnsureMemoryDir()
	fp := getMemoryFilePath(key)

	if _, err := os.Stat(fp); os.IsNotExist(err) {
		return fmt.Sprintf("No memory found with key '%s'", key)
	}

	if err := os.Remove(fp); err != nil {
		return fmt.Sprintf("Error deleting memory '%s': %v", key, err)
	}

	return fmt.Sprintf("Memory '%s' deleted", key)
}

func SearchMemories(query string) string {
	memoryMu.RLock()
	defer memoryMu.RUnlock()

	_ = EnsureMemoryDir()

	entries, err := os.ReadDir(memoryDir)
	if err != nil || len(entries) == 0 {
		return "No memories stored yet."
	}

	var matches []string
	queryLower := strings.ToLower(query)

	for _, entry := range entries {
		if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".md") {
			fp := filepath.Join(memoryDir, entry.Name())
			data, err := os.ReadFile(fp)
			if err == nil && strings.Contains(strings.ToLower(string(data)), queryLower) {
				key := strings.TrimSuffix(entry.Name(), ".md")
				matches = append(matches, fmt.Sprintf("---\n**Memory: %s**\n%s", key, string(data)))
			}
		}
	}

	if len(matches) == 0 {
		return fmt.Sprintf("No memories found containing '%s'", query)
	}

	return fmt.Sprintf("Memories containing '%s':\n\n%s", query, strings.Join(matches, "\n\n"))
}
