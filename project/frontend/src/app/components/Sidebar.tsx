import { MessageSquare, Trash2, X } from 'lucide-react';
import { useAppStore } from '../store';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { cn } from './ui/utils';
import { CreateWorkspaceDialog } from './CreateWorkspaceDialog';

export function Sidebar() {
  const {
    workspaces,
    activeWorkspaceId,
    sidebarOpen,
    deleteWorkspace,
    setActiveWorkspace,
    toggleSidebar,
    setSidebarOpen,
  } = useAppStore();

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-0 h-full bg-zinc-900 border-r border-zinc-800 z-50 transition-transform duration-300 flex flex-col',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
          'w-64'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <h2 className="font-semibold text-white">Agent Testing</h2>
          <Button
            variant="ghost"
            size="sm"
            className="text-zinc-400 hover:text-white"
            onClick={toggleSidebar}
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* New Workspace Button */}
        <div className="p-3">
          <CreateWorkspaceDialog />
        </div>

        {/* Workspaces List */}
        <ScrollArea className="flex-1 px-2">
          <div className="space-y-1 py-2">
            {[...workspaces].reverse().map((workspace) => (
              <div
                key={workspace.id}
                className={cn(
                  'group relative flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors',
                  activeWorkspaceId === workspace.id
                    ? 'bg-zinc-800 text-white'
                    : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-white'
                )}
                onClick={() => {
                  setActiveWorkspace(workspace.id);
                  setSidebarOpen(false);
                }}
              >
                <MessageSquare className="w-4 h-4 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="truncate">{workspace.name}</div>
                  <div className="text-xs text-zinc-500">
                    {workspace.mode === 'api' ? 'API Testing' : 'A/B Testing'}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="opacity-0 group-hover:opacity-100 h-6 w-6 p-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteWorkspace(workspace.id);
                  }}
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            ))}
          </div>
        </ScrollArea>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-800 text-xs text-zinc-500">
          <div>{workspaces.length} workspace(s)</div>
        </div>
      </aside>

    </>
  );
}