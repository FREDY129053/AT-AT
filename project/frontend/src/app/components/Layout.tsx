import { Sidebar } from './Sidebar';
import { WorkspaceView } from './WorkspaceView';
import { useAppStore } from '../store';
import { cn } from './ui/utils';

export function Layout() {
  const { sidebarOpen } = useAppStore();

  return (
    <div className="h-screen w-screen overflow-hidden bg-zinc-50">
      <Sidebar />

      <main
        className={cn(
          'h-full transition-all duration-300',
          sidebarOpen ? 'lg:ml-64' : 'ml-0'
        )}
      >
        <WorkspaceView />
      </main>
    </div>
  );
}
