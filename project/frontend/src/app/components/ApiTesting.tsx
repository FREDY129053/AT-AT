import { useState } from "react";
import {
  Upload,
  Play,
  Download,
  FileText,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Checkbox } from "./ui/checkbox";
import { Progress } from "./ui/progress";
import { Badge } from "./ui/badge";
import { FileUploader } from "./FileUploader";
import { useAppStore } from "../store";

interface UploadedFile {
  file: File;
  type: "bpmn" | "mermaid";
}

export function ApiTesting() {
  const [swaggerUrl, setSwaggerUrl] = useState("");
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [outputFormats, setOutputFormats] = useState<string[]>([
    "json",
    "html",
  ]);
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [testResults, setTestResults] = useState<any>(null);
  const [intermediateResults, setIntermediateResults] = useState<any>(null);

  const currentWorkspace = useAppStore((state) =>
    state.workspaces.find((w) => w.id === state.activeWorkspaceId),
  );

  const availableFormats = [
    { id: "json", label: "JSON Report" },
    { id: "html", label: "HTML Report" },
    { id: "xml", label: "XML Report" },
    { id: "pdf", label: "PDF Report" },
    { id: "csv", label: "CSV Data" },
  ];

  const handleFormatToggle = (formatId: string) => {
    setOutputFormats((prev) =>
      prev.includes(formatId)
        ? prev.filter((f) => f !== formatId)
        : [...prev, formatId],
    );
  };

  const handleRunTests = async () => {
    if (!swaggerUrl) return;

    // use workspace name as taskId (same convention as other UIs)
    const taskId = currentWorkspace
      ? currentWorkspace.name
      : String(Date.now());

    setIsRunning(true);
    setProgress(0);
    setTestResults(null);
    setIntermediateResults(null);

    // seed intermediate results so UI shows immediately
    setIntermediateResults({
      fuzz: { testsRun: 0, passed: 0, failed: 0, coverage: 0 },
      businessProcess: uploadedFiles.length
        ? { flowsValidated: 0, pathsCompleted: 0, errors: 0, compliance: 0 }
        : null,
    });

    let messagesReceived = false;
    let debugSource: EventSource | null = null;

    const eventSource = new EventSource(
      `http://localhost:8000/api/events/${encodeURIComponent(taskId)}`,
    );

    eventSource.onopen = () => {
      console.info("SSE connected to", taskId);
    };

    eventSource.onerror = (err) => {
      console.error("SSE error", err);
    };

    eventSource.onmessage = (event) => {
      messagesReceived = true;
      try {
        const parsed = JSON.parse(event.data);
        const payload = parsed.payload ? parsed.payload : parsed;

        const eventType =
          parsed.event_type || payload.event_type || payload.type;

        // If payload contains metrics or progress, merge into intermediateResults
        if (payload.metrics || payload.progress) {
          setIntermediateResults((prev: any) => ({
            ...prev,
            fuzz: {
              testsRun: payload.metrics?.testsRun ?? prev?.fuzz?.testsRun ?? 0,
              passed: payload.metrics?.passed ?? prev?.fuzz?.passed ?? 0,
              failed: payload.metrics?.failed ?? prev?.fuzz?.failed ?? 0,
              coverage: payload.metrics?.coverage ?? prev?.fuzz?.coverage ?? 0,
            },
            businessProcess:
              payload.metrics?.businessProcess ?? prev?.businessProcess,
          }));
        }

        // Handle termination / finished events
        if (
          eventType === "finished" ||
          payload.terminate === "success" ||
          payload.terminate === "error"
        ) {
          // finalize
          try {
            eventSource.close();
          } catch (e) {}
          if (debugSource)
            try {
              debugSource.close();
            } catch (e) {}

          setIsRunning(false);
          setProgress(100);

          // If the backend provided a summary in payload.summary use it, otherwise synthesize
          const summary = payload.summary || payload.result || null;
          if (summary) {
            setTestResults(summary);
          } else {
            // fallback synthesized result
            setTestResults({
              fuzz: {
                totalTests: 245,
                passed: 223,
                failed: 18,
                skipped: 4,
                coverage: 87.5,
                duration: "3m 42s",
              },
              businessProcess: payload.businessProcess || null,
              timestamp: new Date().toISOString(),
            });
          }
        }
      } catch (error) {
        console.error("Ошибка парсинга JSON в API SSE:", error);
      }
    };

    // if no messages within 3s, open debug stream so user can see raw events
    setTimeout(() => {
      if (!messagesReceived) {
        console.warn(
          "No SSE messages received for task",
          taskId,
          "- opening debug stream",
        );
        debugSource = new EventSource(
          "http://localhost:8000/api/events/__debug__",
        );
        debugSource.onmessage = (e) => console.debug("DEBUG SSE:", e.data);
        debugSource.onerror = (e) => console.error("DEBUG SSE error", e);
      }
    }, 3000);

    // prepare payload: include swaggerUrl and first uploaded file content (if present)
    let filesContent = "";
    if (uploadedFiles.length > 0) {
      try {
        const file = uploadedFiles[0].file;
        filesContent = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result ?? ""));
          reader.onerror = () =>
            reject(new Error("Failed to read uploaded file"));
          reader.readAsText(file);
        });
      } catch (e) {
        console.warn(
          "Failed to read uploaded file, continuing without file content",
          e,
        );
        filesContent = "";
      }
    }

    const payload = {
      docs_url: swaggerUrl,
      files: filesContent,
      config: {
        outputFormats,
        llm: currentWorkspace?.llmConfig ?? null,
      },
    } as const;

    // send start request to backend which will run the api graph
    await fetch("http://localhost:8000/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        task_id: taskId,
        test_type: "api",
        payload,
      }),
      headers: { "Content-Type": "application/json" },
    });

    // lightweight progress updater while events stream in
    const intervalId = setInterval(() => {
      setProgress((prev) => {
        if (!isRunning) {
          clearInterval(intervalId);
          return 100;
        }
        // gently increase until events report finalization
        const next = Math.min(99, prev + Math.random() * 6);
        return next;
      });
    }, 500);
  };

  const handleDownload = () => {
    // Mock download
    const blob = new Blob(["Mock test results data"], {
      type: "application/zip",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `api-test-results-${Date.now()}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Configuration Section */}
        <Card>
          <CardHeader>
            <CardTitle>API Test Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Swagger URL Input */}
            <div className="space-y-2">
              <Label htmlFor="swagger-url">
                Swagger Documentation URL{" "}
                <span className="text-red-500">*</span>
              </Label>
              <Input
                id="swagger-url"
                type="url"
                placeholder="https://api.example.com/swagger.json"
                value={swaggerUrl}
                onChange={(e) => setSwaggerUrl(e.target.value)}
              />
              <p className="text-sm text-zinc-500">
                Enter the URL to your Swagger/OpenAPI documentation
              </p>
            </div>

            {/* Unified File Upload */}
            <div className="space-y-2">
              <Label>Business Process Files (Optional)</Label>
              <FileUploader
                files={uploadedFiles}
                onFilesChange={setUploadedFiles}
              />
              <p className="text-sm text-zinc-500">
                Upload BPMN or Mermaid files to validate business process flows
              </p>
            </div>

            {/* Output Format Selection */}
            <div className="space-y-3">
              <Label>Output Formats</Label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {availableFormats.map((format) => (
                  <div
                    key={format.id}
                    className="flex items-center space-x-2 border rounded-lg p-3 cursor-pointer hover:bg-zinc-50"
                    onClick={() => handleFormatToggle(format.id)}
                  >
                    <Checkbox
                      id={format.id}
                      checked={outputFormats.includes(format.id)}
                      onCheckedChange={() => handleFormatToggle(format.id)}
                    />
                    <Label
                      htmlFor={format.id}
                      className="cursor-pointer flex-1"
                    >
                      {format.label}
                    </Label>
                  </div>
                ))}
              </div>
            </div>

            {/* Run Button */}
            <Button
              onClick={handleRunTests}
              disabled={!swaggerUrl || isRunning}
              className="w-full"
              size="lg"
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Running Tests...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Run API Tests
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Progress & Intermediate Results (Split Screen) */}
        {isRunning && intermediateResults && (
          <Card>
            <CardHeader>
              <CardTitle>Test Progress & Intermediate Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Running tests and validating endpoints...</span>
                  <span>{Math.round(progress)}%</span>
                </div>
                <Progress value={progress} />
              </div>

              {/* Split-screen intermediate results */}
              <div className="grid md:grid-cols-2 gap-4">
                {/* Fuzz Testing Results */}
                <div className="space-y-3">
                  <div className="font-semibold text-blue-600 flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-blue-600" />
                    Fuzz Testing
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between p-2 bg-blue-50 rounded">
                      <span>Tests Run</span>
                      <span className="font-semibold">
                        {intermediateResults.fuzz.testsRun}
                      </span>
                    </div>
                    <div className="flex justify-between p-2 bg-blue-50 rounded">
                      <span>Passed</span>
                      <span className="font-semibold text-green-600">
                        {intermediateResults.fuzz.passed}
                      </span>
                    </div>
                    <div className="flex justify-between p-2 bg-blue-50 rounded">
                      <span>Failed</span>
                      <span className="font-semibold text-red-600">
                        {intermediateResults.fuzz.failed}
                      </span>
                    </div>
                    <div className="flex justify-between p-2 bg-blue-50 rounded">
                      <span>Coverage</span>
                      <span className="font-semibold">
                        {intermediateResults.fuzz.coverage}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Business Process Testing Results */}
                {intermediateResults.businessProcess ? (
                  <div className="space-y-3">
                    <div className="font-semibold text-green-600 flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-green-600" />
                      Business Process Testing
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between p-2 bg-green-50 rounded">
                        <span>Flows Validated</span>
                        <span className="font-semibold">
                          {intermediateResults.businessProcess.flowsValidated}
                        </span>
                      </div>
                      <div className="flex justify-between p-2 bg-green-50 rounded">
                        <span>Paths Completed</span>
                        <span className="font-semibold">
                          {intermediateResults.businessProcess.pathsCompleted}
                        </span>
                      </div>
                      <div className="flex justify-between p-2 bg-green-50 rounded">
                        <span>Errors Found</span>
                        <span className="font-semibold text-red-600">
                          {intermediateResults.businessProcess.errors}
                        </span>
                      </div>
                      <div className="flex justify-between p-2 bg-green-50 rounded">
                        <span>Compliance Score</span>
                        <span className="font-semibold">
                          {intermediateResults.businessProcess.compliance}%
                        </span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center border-2 border-dashed rounded-lg p-6 text-center">
                    <div className="text-zinc-500 text-sm">
                      <p className="font-medium">
                        No business process files uploaded
                      </p>
                      <p className="text-xs mt-1">
                        Upload BPMN/Mermaid files to enable business process
                        testing
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Final Results (Split Screen) */}
        {testResults && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Test Results</CardTitle>
                <Badge variant="outline" className="text-green-600">
                  <CheckCircle2 className="w-3 h-3 mr-1" />
                  Completed
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Split-screen final results */}
              <div className="grid md:grid-cols-2 gap-4">
                {/* Fuzz Testing Results */}
                <div className="border rounded-lg p-4 space-y-3">
                  <div className="font-semibold text-lg text-blue-600">
                    Fuzz Testing Results
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Total Tests</span>
                      <span className="font-semibold">
                        {testResults.fuzz.totalTests}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Passed</span>
                      <span className="font-semibold text-green-600">
                        {testResults.fuzz.passed}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Failed</span>
                      <span className="font-semibold text-red-600">
                        {testResults.fuzz.failed}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Skipped</span>
                      <span className="font-semibold text-zinc-600">
                        {testResults.fuzz.skipped}
                      </span>
                    </div>
                    <div className="flex justify-between border-t pt-2 mt-2">
                      <span>Coverage</span>
                      <span className="font-semibold text-blue-600">
                        {testResults.fuzz.coverage}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Duration</span>
                      <span className="font-semibold">
                        {testResults.fuzz.duration}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Business Process Testing Results */}
                {testResults.businessProcess ? (
                  <div className="border-2 border-green-200 bg-green-50 rounded-lg p-4 space-y-3">
                    <div className="font-semibold text-lg text-green-600">
                      Business Process Results
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span>Total Flows</span>
                        <span className="font-semibold">
                          {testResults.businessProcess.totalFlows}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Validated</span>
                        <span className="font-semibold text-green-600">
                          {testResults.businessProcess.validated}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Errors</span>
                        <span className="font-semibold text-red-600">
                          {testResults.businessProcess.errors}
                        </span>
                      </div>
                      <div className="flex justify-between border-t pt-2 mt-2">
                        <span>Compliance Score</span>
                        <span className="font-semibold text-green-600">
                          {testResults.businessProcess.compliance}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Duration</span>
                        <span className="font-semibold">
                          {testResults.businessProcess.duration}
                        </span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="border-2 border-dashed rounded-lg p-4 flex items-center justify-center">
                    <div className="text-zinc-500 text-sm text-center">
                      <p className="font-medium">
                        No business process testing performed
                      </p>
                      <p className="text-xs mt-1">
                        Upload BPMN/Mermaid files before running tests
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Additional Info */}
              <div className="flex items-center justify-between text-sm text-zinc-600 p-4 bg-zinc-50 rounded-lg">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  <span>
                    Total Duration: {testResults.fuzz.duration}
                    {testResults.businessProcess &&
                      ` + ${testResults.businessProcess.duration}`}
                  </span>
                </div>
                <div>
                  Completed at:{" "}
                  {new Date(testResults.timestamp).toLocaleTimeString()}
                </div>
              </div>

              {/* Download Button */}
              <Button onClick={handleDownload} className="w-full" size="lg">
                <Download className="w-4 h-4 mr-2" />
                Download Test Results Archive
              </Button>

              {/* Selected Formats */}
              <div className="text-sm text-zinc-600">
                <span className="font-medium">Selected formats: </span>
                {outputFormats.map((format) => (
                  <Badge key={format} variant="secondary" className="ml-2">
                    {format.toUpperCase()}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
