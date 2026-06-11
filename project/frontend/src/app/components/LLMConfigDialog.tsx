import { useState, useEffect } from 'react';
import { Brain, Eye, EyeOff } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Slider } from './ui/slider';
import { Button } from './ui/button';
import { LLMConfig, LocalModelType, OnlineProvider } from '../types';
import { useAppStore } from '../store';

interface LLMConfigDialogProps {
  workspaceId: string;
  currentConfig?: LLMConfig;
}

export function LLMConfigDialog({ workspaceId, currentConfig }: LLMConfigDialogProps) {
  const { updateWorkspaceLLM } = useAppStore();
  const [open, setOpen] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  const getDefaultConfig = (): LLMConfig => ({
    type: 'online',
    temperature: 0.7,
  });

  const [config, setConfig] = useState<LLMConfig>(getDefaultConfig());

  useEffect(() => {
    setConfig(currentConfig || getDefaultConfig());
  }, [workspaceId, currentConfig]);

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (newOpen) {
      setConfig(currentConfig || getDefaultConfig());
      setShowApiKey(false);
    }
  };

  const handleSave = () => {
    updateWorkspaceLLM(workspaceId, config);
    handleOpenChange(false);
  };

  const updateConfig = (updates: Partial<LLMConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }));
  };

  const handleTypeChange = (newType: 'local' | 'online') => {
    setConfig((prev) => ({
      ...prev,
      type: newType,
      modelName: undefined, // Очищаем имя модели при смене типа
    }));
  };

  const hasRequiredFields = () => {
    if (config.type === 'local') {
      if (config.localType === 'ollama') {
        return !!config.modelName?.trim();
      }
      if (config.localType === 'llama') {
        return !!config.modelPath?.trim();
      }
    } else if (config.type === 'online') {
      return !!config.provider && !!config.apiKey?.trim() && !!config.modelName?.trim();
    }
    return false;
  };

  const getModelDisplayName = () => {
    if (!currentConfig) return 'Не настроено';
    if (currentConfig.type === 'local') {
      return currentConfig.localType === 'ollama'
        ? `Ollama: ${currentConfig.modelName || 'не указано'}`
        : `Llama: ${currentConfig.modelPath?.split('/').pop() || 'не указано'}`;
    }
    return `${currentConfig.provider}: ${currentConfig.modelName || 'не указано'}`;
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2 text-zinc-600 hover:text-zinc-900">
          <Brain className="w-4 h-4" />
          <span className="hidden sm:inline text-sm">{getModelDisplayName()}</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Настройка LLM модели</DialogTitle>
          <DialogDescription>
            Выберите и настройте модель для этого workspace
          </DialogDescription>
        </DialogHeader>

        <Tabs value={config.type} onValueChange={(val) => handleTypeChange(val as 'local' | 'online')}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="local">Локальная модель</TabsTrigger>
            <TabsTrigger value="online">Онлайн модель</TabsTrigger>
          </TabsList>

          {/* Local Models */}
          <TabsContent value="local" className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label htmlFor="localType">Тип модели *</Label>
              <Select
                value={config.localType}
                onValueChange={(val) => updateConfig({ localType: val as LocalModelType })}
              >
                <SelectTrigger id="localType">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent position="popper">
                  <SelectItem value="ollama">Ollama</SelectItem>
                  <SelectItem value="llama">Llama</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {config.localType === 'ollama' && (
              <div className="space-y-2">
                <Label htmlFor="modelName">Имя модели *</Label>
                <Input
                  id="modelName"
                  placeholder="например: llama3, mistral, codellama"
                  value={config.modelName || ''}
                  onChange={(e) => updateConfig({ modelName: e.target.value })}
                />
              </div>
            )}

            {config.localType === 'llama' && (
              <div className="space-y-2">
                <Label htmlFor="modelPath">Путь к файлу модели *</Label>
                <Input
                  id="modelPath"
                  placeholder="/path/to/model.gguf"
                  value={config.modelPath || ''}
                  onChange={(e) => updateConfig({ modelPath: e.target.value })}
                />
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="seed">Seed (опционально)</Label>
              <Input
                id="seed"
                type="number"
                placeholder="например: 42"
                value={config.seed || ''}
                onChange={(e) => updateConfig({ seed: e.target.value ? parseInt(e.target.value) : undefined })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="temperature-local">
                Temperature: {config.temperature !== undefined ? config.temperature.toFixed(2) : '0.70'}
              </Label>
              <Slider
                id="temperature-local"
                min={0}
                max={2}
                step={0.01}
                value={[config.temperature !== undefined ? config.temperature : 0.7]}
                onValueChange={([val]) => updateConfig({ temperature: val })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxTokens-local">Max Tokens (опционально)</Label>
              <Input
                id="maxTokens-local"
                type="number"
                placeholder="например: 2048"
                value={config.maxTokens || ''}
                onChange={(e) =>
                  updateConfig({ maxTokens: e.target.value ? parseInt(e.target.value) : undefined })
                }
              />
            </div>
          </TabsContent>

          {/* Online Models */}
          <TabsContent value="online" className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label htmlFor="provider">Провайдер *</Label>
              <Select
                value={config.provider}
                onValueChange={(val) => updateConfig({ provider: val as OnlineProvider })}
              >
                <SelectTrigger id="provider">
                  <SelectValue placeholder="Выберите провайдера" />
                </SelectTrigger>
                <SelectContent position="popper">
                  <SelectItem value="OpenAI">OpenAI</SelectItem>
                  <SelectItem value="Anthropic">Anthropic</SelectItem>
                  <SelectItem value="GoogleGenerativeAI">Google Generative AI</SelectItem>
                  <SelectItem value="Groq">Groq</SelectItem>
                  <SelectItem value="AzureChatOpenAI">Azure OpenAI</SelectItem>
                  <SelectItem value="MistralAI">Mistral AI</SelectItem>
                  <SelectItem value="Cohere">Cohere</SelectItem>
                  <SelectItem value="Together">Together</SelectItem>
                  <SelectItem value="DeepSeek">DeepSeek</SelectItem>
                  <SelectItem value="OpenRouter">OpenRouter</SelectItem>
                  <SelectItem value="LiteLLM">LiteLLM</SelectItem>
                  <SelectItem value="HuggingFace">HuggingFace</SelectItem>
                  <SelectItem value="XAI">XAI</SelectItem>
                  <SelectItem value="NVIDIA">NVIDIA</SelectItem>
                  <SelectItem value="Databricks">Databricks</SelectItem>
                  <SelectItem value="Qwen">Qwen</SelectItem>
                  <SelectItem value="GigaChat">GigaChat</SelectItem>
                  <SelectItem value="YandexGPT">Yandex GPT</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="apiKey">API ключ *</Label>
              <div className="relative">
                <Input
                  id="apiKey"
                  type={showApiKey ? 'text' : 'password'}
                  placeholder="sk-..."
                  value={config.apiKey || ''}
                  onChange={(e) => updateConfig({ apiKey: e.target.value })}
                  className="pr-10"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                  onClick={() => setShowApiKey(!showApiKey)}
                >
                  {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="modelName-online">Название модели *</Label>
              <Input
                id="modelName-online"
                placeholder="например: gpt-4, claude-3-opus"
                value={config.modelName || ''}
                onChange={(e) => updateConfig({ modelName: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="temperature-online">
                Temperature: {config.temperature !== undefined ? config.temperature.toFixed(2) : '0.70'}
              </Label>
              <Slider
                id="temperature-online"
                min={0}
                max={2}
                step={0.01}
                value={[config.temperature !== undefined ? config.temperature : 0.7]}
                onValueChange={([val]) => updateConfig({ temperature: val })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxTokens-online">Max Tokens (опционально)</Label>
              <Input
                id="maxTokens-online"
                type="number"
                placeholder="например: 4096"
                value={config.maxTokens || ''}
                onChange={(e) =>
                  updateConfig({ maxTokens: e.target.value ? parseInt(e.target.value) : undefined })
                }
              />
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Отмена
          </Button>
          <Button onClick={handleSave} disabled={!hasRequiredFields()}>
            Сохранить
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
