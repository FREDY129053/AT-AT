import { Menu, Plus, FlaskConical } from 'lucide-react';
import { useAppStore } from '../store';
import { ApiTesting } from './ApiTesting';
import { AbTesting } from './AbTesting';
import { CreateWorkspaceDialog } from './CreateWorkspaceDialog';
import { LLMConfigDialog } from './LLMConfigDialog';
import { Button } from './ui/button';

export function WorkspaceView() {
  const { workspaces, activeWorkspaceId, sidebarOpen, toggleSidebar } = useAppStore();

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId);

  // Welcome screen when no workspaces exist at all
  if (workspaces.length === 0) {
    return (
      <div className="h-full flex flex-col">
        <div className="p-4">
          {!sidebarOpen && (
            <Button variant="ghost" size="sm" onClick={toggleSidebar} className="text-zinc-500 hover:text-zinc-900">
              <Menu className="w-5 h-5" />
            </Button>
          )}
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-sm px-6">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-2xl bg-zinc-100 flex items-center justify-center">
                <FlaskConical className="w-8 h-8 text-zinc-400" />
              </div>
            </div>
            <h2 className="text-xl font-semibold text-zinc-900 mb-2">
              Создайте пространство для работы
            </h2>
            <p className="text-sm text-zinc-500 mb-8 leading-relaxed">
              Workspace позволяет настроить и запустить API или A/B тестирование в одном месте
            </p>
            <CreateWorkspaceDialog
              trigger={
                <Button size="lg" className="gap-2">
                  <Plus className="w-4 h-4" />
                  Add Workspace
                </Button>
              }
            />
          </div>
        </div>
      </div>
    );
  }

  // No active workspace selected (but workspaces exist)
  if (!activeWorkspace) {
    return (
      <div className="h-full flex flex-col">
        <div className="p-4">
          {!sidebarOpen && (
            <Button variant="ghost" size="sm" onClick={toggleSidebar} className="text-zinc-500 hover:text-zinc-900">
              <Menu className="w-5 h-5" />
            </Button>
          )}
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-zinc-500">
            <p className="text-lg">Workspace не выбран</p>
            <p className="text-sm mt-2">Выберите workspace в боковой панели</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b bg-white px-4 py-3 flex items-center gap-3">
        {!sidebarOpen && (
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleSidebar}
            className="flex-shrink-0 text-zinc-500 hover:text-zinc-900 -ml-1"
          >
            <Menu className="w-5 h-5" />
          </Button>
        )}
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold leading-tight truncate">{activeWorkspace.name}</h1>
          <p className="text-xs text-zinc-500">
            {activeWorkspace.mode === 'api' ? 'API Testing' : 'A/B Testing'}
          </p>
        </div>
        <LLMConfigDialog workspaceId={activeWorkspace.id} currentConfig={activeWorkspace.llmConfig} />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeWorkspace.mode === 'api' ? <ApiTesting /> : <AbTesting />}
      </div>
    </div>
  );
}
