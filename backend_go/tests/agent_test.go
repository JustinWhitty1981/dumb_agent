package tests

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"jada-backend/pkg/formatters"
	"jada-backend/pkg/mcp"
	"jada-backend/pkg/memory"
	"jada-backend/pkg/tools"
)

func TestCurrentTimeTool(t *testing.T) {
	res, err := tools.GetCurrentTime()
	if err != nil {
		t.Fatalf("GetCurrentTime returned error: %v", err)
	}
	if !strings.Contains(res, "Current UTC time") && !strings.Contains(res, "Current Local time") {
		t.Errorf("Unexpected GetCurrentTime result: %s", res)
	}
}

func TestMemoryLifecycle(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "test_memory_dir")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	memory.SetMemoryDir(tmpDir)

	testKey := "test_gold_preference_unit"
	testContent := "User tracks the live market price of gold."

	// 1. Save memory
	saveRes := memory.SaveMemory(testKey, testContent)
	if !strings.Contains(saveRes, testKey) {
		t.Errorf("SaveMemory failed: %s", saveRes)
	}

	// 2. Get memory
	getRes := memory.GetMemory(testKey)
	if !strings.Contains(getRes, testContent) {
		t.Errorf("GetMemory failed: %s", getRes)
	}

	// 3. List memories
	listRes := memory.ListMemories()
	if !strings.Contains(listRes, testKey) {
		t.Errorf("ListMemories failed: %s", listRes)
	}

	// 4. Delete memory
	delRes := memory.DeleteMemory(testKey)
	if !strings.Contains(delRes, "deleted") {
		t.Errorf("DeleteMemory failed: %s", delRes)
	}

	// Check file removed
	fp := filepath.Join(tmpDir, testKey+".md")
	if _, err := os.Stat(fp); !os.IsNotExist(err) {
		t.Errorf("Memory file still exists after deletion: %s", fp)
	}
}

func TestFormatters(t *testing.T) {
	// Paint defects sample data
	data := []map[string]interface{}{
		{"door_grade": "pass", "is_fail": 0},
		{"door_grade": "fail", "is_fail": 1, "reason_description": "Scratch on surface"},
	}

	summary := formatters.SummarizePaintDefectsData(data)
	if !strings.Contains(summary, "Total Inspected Doors") || !strings.Contains(summary, "Scratch on surface") {
		t.Errorf("SummarizePaintDefectsData result invalid: %s", summary)
	}

	// Truncation
	longStr := strings.Repeat("A", 15000)
	truncated := formatters.TruncateToolOutput(longStr, 1000)
	if len(truncated) >= 15000 || !strings.Contains(truncated, "truncated") {
		t.Errorf("TruncateToolOutput failed to truncate properly")
	}
}

func TestMCPSanitizer(t *testing.T) {
	args := map[string]interface{}{
		"start_ts": "now-4h",
		"end_ts":   "now",
	}

	sanitized := mcp.SanitizeMCPToolArgs("paint_defects", args)
	startTS, ok := sanitized["start_ts"].(string)
	if !ok || !strings.HasSuffix(startTS, "Z") {
		t.Errorf("SanitizeMCPToolArgs failed to produce ISO UTC timestamp for start_ts: %v", sanitized["start_ts"])
	}

	insightsArgs := mcp.SanitizeMCPToolArgs("InsightsPublish", map[string]interface{}{})
	if insightsArgs["agent_name"] != "J.A.D.A" {
		t.Errorf("SanitizeMCPToolArgs failed to enforce agent_name = J.A.D.A")
	}
}
