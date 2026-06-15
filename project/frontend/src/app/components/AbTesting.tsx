import { useState } from "react";
import { Play, Download, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Checkbox } from "./ui/checkbox";
import { Progress } from "./ui/progress";
import { Badge } from "./ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { TestGroup, GroupType } from "../types";
import { useAppStore } from "../store";

const COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#f97316",
];

const GROUP_TYPES: { value: GroupType; label: string }[] = [
  { value: "teen_student", label: "Школьники" },
  { value: "poor_worker", label: "Малоимущие" },
  { value: "young_professional", label: "Молодые специалисты" },
  { value: "middle_class_parent", label: "Семейные" },
  { value: "retired", label: "Пенсионеры" },
  { value: "college_student", label: "Студенты" },
  { value: "unemployed", label: "Безработные" },
];

function toEven(n: number): number {
  const v = Math.max(2, Math.abs(Math.round(n)));
  return v % 2 === 0 ? v : v - 1;
}

export function AbTesting() {
  const [interfaceA, setInterfaceA] = useState("");
  const [interfaceB, setInterfaceB] = useState("");
  const [targetAction, setTargetAction] = useState("");
  const [groups, setGroups] = useState<TestGroup[]>([
    { id: "1", name: "Group A", count: 10, color: COLORS[0] },
    { id: "2", name: "Group B", count: 10, color: COLORS[1] },
    { id: "3", name: "Group C", count: 10, color: COLORS[2] },
    { id: "4", name: "Group D", count: 10, color: COLORS[3] },
  ]);
  const [selectedGroups, setSelectedGroups] = useState<string[]>([
    "1",
    "2",
    "3",
    "4",
  ]);
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [testResults, setTestResults] = useState<any>(null);
  const [intermediateResults, setIntermediateResults] = useState<any>(null);
  // const [activeAgentsA, setActiveAgentsA] = useState(0);
  // const [activeAgentsB, setActiveAgentsB] = useState(0);

  const currentWorkspace = useAppStore((state) =>
    state.workspaces.find((w) => w.id === state.activeWorkspaceId),
  );

  const handleGroupToggle = (groupId: string) => {
    setSelectedGroups((prev) =>
      prev.includes(groupId)
        ? prev.filter((id) => id !== groupId)
        : [...prev, groupId],
    );
  };

  const handleCountChange = (groupId: string, raw: string) => {
    const parsed = parseInt(raw);
    if (isNaN(parsed)) return;
    const even = toEven(parsed);
    setGroups((prev) =>
      prev.map((g) => (g.id === groupId ? { ...g, count: even } : g)),
    );
  };

  // Round to nearest even on blur in case user typed an odd number
  const handleCountBlur = (groupId: string, raw: string) => {
    const parsed = parseInt(raw);
    if (isNaN(parsed)) {
      setGroups((prev) =>
        prev.map((g) => (g.id === groupId ? { ...g, count: 2 } : g)),
      );
      return;
    }
    const even = toEven(parsed);
    setGroups((prev) =>
      prev.map((g) => (g.id === groupId ? { ...g, count: even } : g)),
    );
  };

  const handleGroupTypeChange = (groupId: string, type: GroupType) => {
    setGroups((prev) =>
      prev.map((g) => (g.id === groupId ? { ...g, type } : g)),
    );
  };

  const getAvailableTypes = (currentGroupId: string): GroupType[] => {
    const usedTypes = groups
      .filter((g) => g.id !== currentGroupId && g.type)
      .map((g) => g.type as GroupType);
    return GROUP_TYPES.map((t) => t.value).filter(
      (type) => !usedTypes.includes(type),
    );
  };

  const handleAddGroup = () => {
    if (groups.length < GROUP_TYPES.length) {
      const newId = Date.now().toString();
      const newGroup: TestGroup = {
        id: newId,
        name: `Group ${String.fromCharCode(65 + groups.length)}`,
        count: 10,
        color: COLORS[groups.length % COLORS.length],
      };
      setGroups([...groups, newGroup]);
      setSelectedGroups([...selectedGroups, newId]);
    }
  };

  const handleRemoveGroup = (groupId: string) => {
    if (groups.length > 1) {
      setGroups(groups.filter((g) => g.id !== groupId));
      setSelectedGroups(selectedGroups.filter((id) => id !== groupId));
    }
  };

  const activeGroups = groups.filter((g) => selectedGroups.includes(g.id));
  const totalCount = activeGroups.reduce((sum, g) => sum + g.count, 0);

  const chartData = activeGroups.map((g) => ({
    name: g.name,
    value: totalCount > 0 ? Math.round((g.count / totalCount) * 1000) / 10 : 0,
    count: g.count,
    color: g.color,
  }));

  const handleRunTests = async () => {
    if (
      !interfaceA ||
      !interfaceB ||
      !targetAction ||
      activeGroups.length === 0
    )
      return;

    // const taskId = currentWorkspace!.name;
    const taskId = "99";

    const eventSource = new EventSource(
      `http://localhost:8000/api/events/${taskId}`,
    );

    let activeAgentsA = totalCount / 2;
    let activeAgentsB = totalCount / 2;

    eventSource.onmessage = (event) => {
      console.log("RAW:", event.data); // покажет строку без парсинга
      
      try {
        const parsed = JSON.parse(event.data);
        console.log("Parsed:", parsed);
      } catch (error) {
        console.error("Ошибка парсинга JSON:", error);
      }
    };

    await fetch("http://localhost:8000/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        task_id: taskId,
        test_type: "ui",
        payload: {
          interface_a: interfaceA,
          interface_b: interfaceB,
          intent: targetAction,
          groups: activeGroups,
          llm: currentWorkspace!.llmConfig,
        },
      }),
      headers: {
        "Content-Type": "application/json",
      },
    });

    
    setIsRunning(true);
    setProgress(0);
    setTestResults(null);
    setIntermediateResults(null);

    console.log(totalCount)

    const interval = setInterval(() => {
      setProgress((prev) => {
        const next = prev + 0.1;

        if (next < 100) {
          // if (next > 20 && next < 100) {
          setIntermediateResults({
            interfaceA: {
              activeAgents: activeAgentsA,
              tokens: Math.round((next / 100) * 345),
              time: "2m 34s",
            },
            interfaceB: {
              activeAgents: activeAgentsB,
              tokens: Math.round((next / 100) * 398),
              time: "3m 12s",
            },
          });
        }

        if (next >= 100) {
          eventSource.close()
          clearInterval(interval);
          setIsRunning(false);
          setTestResults({
            interfaceA: {
              activeAgents: activeAgentsA,
              tokens: 345,
              time: "2m 34s",
            },
            interfaceB: {
              activeAgents: activeAgentsB,
              tokens: 398,
              time: "3m 12s",
            },
            winner: "B",
            confidence: 94.2,
            duration: "4h 23m",
            timestamp: new Date().toISOString(),
          });
          return 100;
        }
        return next;
      });
    }, 500);
  };

  const handleDownload = () => {
    const blob = new Blob(["Mock A/B test results data"], {
      type: "application/zip",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ab-test-results-${Date.now()}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-6xl mx-auto p-6 space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>A/B Test Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Interface URLs */}
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="interface-a">
                  Interface A URL <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="interface-a"
                  type="url"
                  placeholder="https://app.example.com/variant-a"
                  value={interfaceA}
                  onChange={(e) => setInterfaceA(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="interface-b">
                  Interface B URL <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="interface-b"
                  type="url"
                  placeholder="https://app.example.com/variant-b"
                  value={interfaceB}
                  onChange={(e) => setInterfaceB(e.target.value)}
                />
              </div>
            </div>

            {/* Target Action */}
            <div className="space-y-2">
              <Label htmlFor="target-action">
                Целевое действие <span className="text-red-500">*</span>
              </Label>
              <Input
                id="target-action"
                placeholder="Например: нажатие на кнопку «Купить», регистрация, добавление в корзину"
                value={targetAction}
                onChange={(e) => setTargetAction(e.target.value)}
              />
            </div>

            {/* Group Distribution */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label>Группы и объёмы</Label>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-zinc-600">
                    Итого: {totalCount} чел.
                  </Badge>
                  {groups.length < GROUP_TYPES.length && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleAddGroup}
                    >
                      Add Group
                    </Button>
                  )}
                </div>
              </div>

              <div className="grid lg:grid-cols-2 gap-6">
                {/* Groups List */}
                <div className="space-y-3">
                  {groups.map((group) => {
                    const availableTypes = getAvailableTypes(group.id);
                    const isActive = selectedGroups.includes(group.id);
                    return (
                      <div
                        key={group.id}
                        className="flex flex-col gap-2 p-3 border rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <Checkbox
                            id={`group-${group.id}`}
                            checked={isActive}
                            onCheckedChange={() => handleGroupToggle(group.id)}
                          />
                          <div
                            className="w-4 h-4 rounded-full flex-shrink-0"
                            style={{ backgroundColor: group.color }}
                          />
                          <Label
                            htmlFor={`group-${group.id}`}
                            className="flex-1 cursor-pointer"
                          >
                            {group.name}
                          </Label>
                          <Input
                            type="number"
                            min="2"
                            step="2"
                            value={group.count}
                            onChange={(e) =>
                              handleCountChange(group.id, e.target.value)
                            }
                            onBlur={(e) =>
                              handleCountBlur(group.id, e.target.value)
                            }
                            disabled={!isActive}
                            className="w-24 text-center"
                          />
                          <span className="text-sm text-zinc-500 w-8">
                            чел.
                          </span>
                          {groups.length > 1 && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRemoveGroup(group.id)}
                              className="h-8 w-8 p-0 text-zinc-400 hover:text-red-500"
                            >
                              ×
                            </Button>
                          )}
                        </div>
                        <div className="ml-9 flex items-center gap-2">
                          <Label className="text-sm text-zinc-500 whitespace-nowrap">
                            Тип группы:
                          </Label>
                          <Select
                            value={group.type || ""}
                            onValueChange={(value) =>
                              handleGroupTypeChange(
                                group.id,
                                value as GroupType,
                              )
                            }
                            disabled={!isActive}
                          >
                            <SelectTrigger className="w-40">
                              <SelectValue placeholder="Выберите тип" />
                            </SelectTrigger>
                            <SelectContent>
                              {GROUP_TYPES.map((typeOption) => {
                                const isAvailable =
                                  availableTypes.includes(typeOption.value) ||
                                  group.type === typeOption.value;
                                return (
                                  <SelectItem
                                    key={typeOption.value}
                                    value={typeOption.value}
                                    disabled={!isAvailable}
                                  >
                                    {typeOption.label}
                                    {!isAvailable && " (уже используется)"}
                                  </SelectItem>
                                );
                              })}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Pie Chart — percentages derived from counts */}
                <div className="flex flex-col items-center justify-center border rounded-lg p-4 bg-zinc-50">
                  {chartData.length > 0 ? (
                    <>
                      <ResponsiveContainer width="100%" height={250}>
                        <PieChart>
                          <Pie
                            data={chartData}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ name, value }) => `${name}: ${value}%`}
                            outerRadius={80}
                            dataKey="value"
                          >
                            {chartData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip
                            formatter={(
                              value: number,
                              _name: string,
                              props: any,
                            ) => [
                              `${value}% (${props.payload.count} чел.)`,
                              props.payload.name,
                            ]}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="text-sm text-zinc-500 mt-1">
                        {activeGroups.length} групп · {totalCount} чел. всего
                      </div>
                    </>
                  ) : (
                    <div className="text-zinc-400 text-center py-12 text-sm">
                      Выберите хотя бы одну группу для отображения диаграммы
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Run Button */}
            <Button
              onClick={handleRunTests}
              disabled={
                !interfaceA ||
                !interfaceB ||
                !targetAction ||
                activeGroups.length === 0 ||
                isRunning
              }
              className="w-full"
              size="lg"
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Running A/B Tests...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Run A/B Tests
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Progress & Intermediate Results */}
        {isRunning && intermediateResults && (
          <Card>
            <CardHeader>
              <CardTitle>Test Progress & Intermediate Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Running tests across selected groups...</span>
                  <span>{Math.round(progress)}%</span>
                </div>
                <Progress value={progress} />
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-3">
                  <div className="font-semibold text-blue-600 flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-blue-600" />
                    Interface A
                  </div>
                  <div className="space-y-2 text-sm">
                    {(["activeAgents", "tokens", "time"] as const).map(
                      (key) => (
                        <div
                          key={key}
                          className="flex justify-between p-2 bg-blue-50 rounded"
                        >
                          <span className="capitalize">
                            {key === "time"
                              ? "Time"
                              : key === "activeAgents"
                                ? "Active Agents"
                                : key}
                          </span>
                          <span className="font-semibold">
                            {intermediateResults.interfaceA[key]}
                            {/* {key === "bounceRate" ? "%" : ""} */}
                          </span>
                        </div>
                      ),
                    )}
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="font-semibold text-green-600 flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-green-600" />
                    Interface B
                  </div>
                  <div className="space-y-2 text-sm">
                    {(["activeAgents", "tokens", "time"] as const).map(
                      (key) => (
                        <div
                          key={key}
                          className="flex justify-between p-2 bg-green-50 rounded"
                        >
                          <span className="capitalize">
                            {key === "time"
                              ? "Time"
                              : key === "activeAgents"
                                ? "Active Agents"
                                : key}
                          </span>
                          <span className="font-semibold">
                            {intermediateResults.interfaceB[key]}
                            {/* {key === "bounceRate" ? "%" : ""} */}
                          </span>
                        </div>
                      ),
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Final Results */}
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
              <div className="p-4 bg-green-50 border-2 border-green-200 rounded-lg text-center">
                <div className="text-2xl font-semibold text-green-700">
                  Interface {testResults.winner} is the Winner!
                </div>
                <div className="text-sm text-green-600 mt-1">
                  Statistical confidence: {testResults.confidence}%
                </div>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="border rounded-lg p-4 space-y-3">
                  <div className="font-semibold text-lg text-blue-600">
                    Interface A
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Active Agents</span>
                      <span className="font-semibold">
                        {testResults.interfaceA.activeAgents}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Tokens</span>
                      <span className="font-semibold">
                        {testResults.interfaceA.tokens}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Time</span>
                      <span className="font-semibold">
                        {testResults.interfaceA.time}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="border-2 border-green-200 bg-green-50 rounded-lg p-4 space-y-3">
                  <div className="font-semibold text-lg text-green-600">
                    Interface B
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Active Agents</span>
                      <span className="font-semibold">
                        {testResults.interfaceB.activeAgents}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Tokens</span>
                      <span className="font-semibold">
                        {testResults.interfaceB.tokens}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Time</span>
                      <span className="font-semibold">
                        {testResults.interfaceB.time}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between text-sm text-zinc-600 p-4 bg-zinc-50 rounded-lg">
                <div>Duration: {testResults.duration}</div>
                <div>
                  Completed at:{" "}
                  {new Date(testResults.timestamp).toLocaleTimeString()}
                </div>
              </div>
              <Button onClick={handleDownload} className="w-full" size="lg">
                <Download className="w-4 h-4 mr-2" />
                Download Test Results Archive
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
