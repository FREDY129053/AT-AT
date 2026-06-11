export type TestingMode = 'api' | 'ab';

export type LocalModelType = 'ollama' | 'llama';

export type OnlineProvider =
  | 'OpenAI'
  | 'Anthropic'
  | 'GoogleGenerativeAI'
  | 'AzureChatOpenAI'
  | 'Groq'
  | 'HuggingFace'
  | 'XAI'
  | 'NVIDIA'
  | 'Cohere'
  | 'MistralAI'
  | 'Together'
  | 'DeepSeek'
  | 'Databricks'
  | 'Qwen'
  | 'GigaChat'
  | 'YandexGPT'
  | 'OpenRouter'
  | 'LiteLLM';

export interface LLMConfig {
  type: 'local' | 'online';

  // Для локальных моделей
  localType?: LocalModelType;
  modelName?: string; // для Ollama
  modelPath?: string; // для Llama
  seed?: number;

  // Для онлайн моделей
  provider?: OnlineProvider;
  apiKey?: string;

  // Общие параметры
  temperature?: number;
  maxTokens?: number;
}

export interface Workspace {
  id: string;
  name: string;
  mode: TestingMode;
  createdAt: Date;
  llmConfig?: LLMConfig;
}

export interface ApiTestConfig {
  swaggerUrl: string;
  bpmnFile?: File;
  mermaidFile?: File;
  outputFormats: string[];
}

export type GroupType = 'children' | 'teenagers' | 'adults' | 'elderly';

export interface TestGroup {
  id: string;
  name: string;
  count: number;
  color: string;
  type?: GroupType;
}

export interface AbTestConfig {
  interfaceA: string;
  interfaceB: string;
  targetAction: string;
  groups: TestGroup[];
  selectedGroups: string[];
}

export interface TestResult {
  id: string;
  timestamp: Date;
  status: 'running' | 'completed' | 'failed';
  progress: number;
  downloadUrl?: string;
}
