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

    console.log(currentWorkspace?.name);
    console.log(currentWorkspace?.llmConfig)

    setIsRunning(true);
    setProgress(0);
    setTestResults(null);
    setIntermediateResults(null);

    const hasBusinessProcessFiles = uploadedFiles.length > 0;

    // Simulate test execution
    const interval = setInterval(() => {
      setProgress((prev) => {
        const newProgress = prev + Math.random() * 8;

        // Update intermediate results
        if (newProgress > 20 && newProgress < 100) {
          setIntermediateResults({
            fuzz: {
              testsRun: Math.round((newProgress / 100) * 245),
              passed: Math.round((newProgress / 100) * 223),
              failed: Math.round((newProgress / 100) * 18),
              coverage: Math.round((newProgress / 100) * 87.5),
            },
            businessProcess: hasBusinessProcessFiles
              ? {
                  flowsValidated: Math.round((newProgress / 100) * 12),
                  pathsCompleted: Math.round((newProgress / 100) * 45),
                  errors: Math.round((newProgress / 100) * 3),
                  compliance: Math.round((newProgress / 100) * 94.2),
                }
              : null,
          });
        }

        if (newProgress >= 100) {
          clearInterval(interval);
          setIsRunning(false);
          setTestResults({
            fuzz: {
              totalTests: 245,
              passed: 223,
              failed: 18,
              skipped: 4,
              coverage: 87.5,
              duration: "3m 42s",
            },
            businessProcess: hasBusinessProcessFiles
              ? {
                  totalFlows: 12,
                  validated: 11,
                  errors: 3,
                  compliance: 94.2,
                  duration: "2m 18s",
                }
              : null,
            timestamp: new Date().toISOString(),
          });
          return 100;
        }
        return newProgress;
      });
    }, 400);
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
