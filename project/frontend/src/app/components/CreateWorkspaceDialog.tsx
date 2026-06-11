import { useState } from 'react';
import { Plus } from 'lucide-react';
import { useAppStore } from '../store';
import { Button } from './ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { RadioGroup, RadioGroupItem } from './ui/radio-group';
import { TestingMode } from '../types';

interface Props {
  trigger?: React.ReactNode;
  onCreated?: () => void;
}

export function CreateWorkspaceDialog({ trigger, onCreated }: Props) {
  const { workspaces, workspaceCounter, addWorkspace, setSidebarOpen } = useAppStore();

  const [name, setName] = useState('');
  const [mode, setMode] = useState<TestingMode>('api');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [nameError, setNameError] = useState('');

  const defaultName = `Workspace ${workspaceCounter}`;

  const validate = (value: string): string => {
    const trimmed = value.trim();
    const resolved = trimmed || defaultName;
    const duplicate = workspaces.some(
      (w) => w.name.toLowerCase() === resolved.toLowerCase()
    );
    if (duplicate) return `Пространство с именем «${resolved}» уже существует`;
    return '';
  };

  const handleCreate = () => {
    const error = validate(name);
    if (error) {
      setNameError(error);
      return;
    }
    addWorkspace(name.trim() || undefined, mode);
    setName('');
    setMode('api');
    setNameError('');
    setDialogOpen(false);
    setSidebarOpen(false);
    onCreated?.();
  };

  return (
    <Dialog
      open={dialogOpen}
      onOpenChange={(open) => {
        setDialogOpen(open);
        if (!open) {
          setName('');
          setNameError('');
          setMode('api');
        }
      }}
    >
      <DialogTrigger asChild>
        {trigger ?? (
          <Button className="w-full" variant="outline">
            <Plus className="w-4 h-4 mr-2" />
            New Workspace
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Workspace</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="workspace-name">
              Название{' '}
              <span className="text-zinc-400 font-normal text-sm">(необязательно)</span>
            </Label>
            <Input
              id="workspace-name"
              placeholder={defaultName}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setNameError('');
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreate();
              }}
              className={nameError ? 'border-red-500 focus-visible:ring-red-500' : ''}
            />
            {nameError ? (
              <p className="text-sm text-red-500">{nameError}</p>
            ) : (
              <p className="text-xs text-zinc-400">
                Оставьте пустым — будет использовано «{defaultName}»
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label>Режим тестирования</Label>
            <RadioGroup
              value={mode}
              onValueChange={(value) => setMode(value as TestingMode)}
            >
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="api" id="mode-api" />
                <Label htmlFor="mode-api" className="cursor-pointer">
                  API Testing
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="ab" id="mode-ab" />
                <Label htmlFor="mode-ab" className="cursor-pointer">
                  A/B Testing
                </Label>
              </div>
            </RadioGroup>
          </div>
          <Button onClick={handleCreate} className="w-full">
            Create Workspace
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
