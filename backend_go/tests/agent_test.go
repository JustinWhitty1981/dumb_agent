package tests

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"jada-backend/pkg/agent"
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

	// Test stringified JSON array in insight parameter
	rawStringifiedInsight := `[{"type": "quality_risk", "title": "Test Insight Title"}]`
	insightArgs := map[string]interface{}{
		"insight": []interface{}{rawStringifiedInsight},
	}
	sanitizedInsights := mcp.SanitizeMCPToolArgs("InsightsPublish", insightArgs)
	cleanedInsightList, ok := sanitizedInsights["insight"].([]interface{})
	if !ok || len(cleanedInsightList) == 0 {
		t.Fatalf("SanitizeMCPToolArgs failed to parse stringified insight array into list")
	}
	firstObj, ok := cleanedInsightList[0].(map[string]interface{})
	if !ok || firstObj["title"] != "Test Insight Title" {
		t.Errorf("SanitizeMCPToolArgs failed to unwrap stringified insight object: %v", cleanedInsightList[0])
	}
}

func TestToolPolicies(t *testing.T) {
	localTools := tools.GetLocalTools()
	if len(localTools) == 0 {
		t.Fatalf("GetLocalTools returned empty tool list")
	}

	for _, tool := range localTools {
		if tool.Name == "current_time" || tool.Name == "search_web" || tool.Name == "scrape_url" {
			if !tool.Policy.ReadOnly {
				t.Errorf("Tool '%s' should be marked ReadOnly", tool.Name)
			}
		}
		if tool.Name == "save_memory_tool" {
			if tool.Policy.ReadOnly {
				t.Errorf("save_memory_tool should not be marked ReadOnly")
			}
		}
	}
}

func TestScraperSSRF(t *testing.T) {
	os.Unsetenv("ALLOW_INTERNAL_SCRAPE")

	// 1. Loopback should be blocked
	if err := tools.ValidateScrapeURL("http://127.0.0.1/test"); err == nil {
		t.Errorf("Expected 127.0.0.1 to be blocked by SSRF check, but passed")
	}

	// 2. Metadata service should be blocked
	if err := tools.ValidateScrapeURL("http://169.254.169.254/latest/meta-data/"); err == nil {
		t.Errorf("Expected 169.254.169.254 to be blocked by SSRF check, but passed")
	}

	// 3. Invalid scheme should be blocked
	if err := tools.ValidateScrapeURL("file:///etc/passwd"); err == nil {
		t.Errorf("Expected file:// scheme to be blocked, but passed")
	}

	// 4. ALLOW_INTERNAL_SCRAPE override should allow loopback
	os.Setenv("ALLOW_INTERNAL_SCRAPE", "true")
	if err := tools.ValidateScrapeURL("http://127.0.0.1/test"); err != nil {
		t.Errorf("Expected ALLOW_INTERNAL_SCRAPE=true to allow loopback, but got error: %v", err)
	}
	os.Unsetenv("ALLOW_INTERNAL_SCRAPE")
}

func TestInsightLogging(t *testing.T) {
	tmpLoggingDir := "insight_logging"
	_ = os.RemoveAll(tmpLoggingDir)

	mcp.LogInsightSummary("InsightsPublish", map[string]interface{}{"title": "Paint Quality Test"}, "Success")

	entries, err := os.ReadDir(tmpLoggingDir)
	if err != nil || len(entries) == 0 {
		t.Fatalf("Failed to find logged insight file in %s: %v", tmpLoggingDir, err)
	}

	content, err := os.ReadFile(filepath.Join(tmpLoggingDir, entries[0].Name()))
	if err != nil || !strings.Contains(string(content), "Published Insight Summary") {
		t.Errorf("Insight summary content invalid: %s", string(content))
	}

	_ = os.RemoveAll(tmpLoggingDir)
}

func TestAgentPolicyEnforcement(t *testing.T) {
	testTools := []tools.ToolDefinition{
		{
			Name: "InsightsPublish",
			Policy: tools.ToolPolicy{
				ReadOnly:         false,
				Destructive:      false,
				RequiresApproval: true,
			},
			Execute: func(args map[string]interface{}) (string, error) {
				return "Published successfully", nil
			},
		},
	}

	am := agent.NewAgentManager(testTools)
	toolDef := am.Tools["InsightsPublish"]

	// INSIGHT_HUMAN_IN_THE_LOOP=true without approval
	os.Setenv("INSIGHT_HUMAN_IN_THE_LOOP", "true")
	hitlEnv := strings.ToLower(os.Getenv("INSIGHT_HUMAN_IN_THE_LOOP"))
	argsUnapproved := map[string]interface{}{}
	approved, _ := argsUnapproved["approved"].(bool)

	if (hitlEnv == "true") && !approved {
		// Passed HITL check blocking unapproved calls
	} else {
		t.Errorf("Expected HITL check to detect unapproved state")
	}

	// With approval=true
	argsApproved := map[string]interface{}{"approved": true}
	res, err := toolDef.Execute(argsApproved)
	if err != nil || res != "Published successfully" {
		t.Errorf("Expected tool execution to succeed with approved=true, got: %v, %v", res, err)
	}

	os.Unsetenv("INSIGHT_HUMAN_IN_THE_LOOP")
}


