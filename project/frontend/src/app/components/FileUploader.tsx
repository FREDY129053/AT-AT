import { Upload, X, FileText } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { useState } from 'react';

interface UploadedFile {
  file: File;
  type: 'bpmn' | 'mermaid';
}

interface FileUploaderProps {
  files: UploadedFile[];
  onFilesChange: (files: UploadedFile[]) => void;
}

export function FileUploader({ files, onFilesChange }: FileUploaderProps) {
  const [dragActive, setDragActive] = useState(false);

  const getFileType = (file: File): 'bpmn' | 'mermaid' | null => {
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (extension === 'bpmn') return 'bpmn';
    if (extension === 'mmd' || extension === 'mermaid') return 'mermaid';
    return null;
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = Array.from(e.target.files || []);
    processFiles(newFiles);
  };

  const processFiles = (newFiles: File[]) => {
    const validFiles: UploadedFile[] = newFiles
      .map((file) => {
        const type = getFileType(file);
        if (type) return { file, type };
        return null;
      })
      .filter((f): f is UploadedFile => f !== null);

    onFilesChange([...files, ...validFiles]);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    processFiles(droppedFiles);
  };

  const removeFile = (index: number) => {
    onFilesChange(files.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      {/* Upload Area */}
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
          dragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-zinc-300 hover:border-zinc-400 hover:bg-zinc-50'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => document.getElementById('file-upload-input')?.click()}
      >
        <input
          id="file-upload-input"
          type="file"
          multiple
          accept=".bpmn,.mmd,.mermaid"
          onChange={handleFileInput}
          className="hidden"
        />
        <Upload className="w-8 h-8 mx-auto text-zinc-400 mb-2" />
        <p className="text-sm font-medium text-zinc-700">
          Click to upload or drag and drop
        </p>
        <p className="text-xs text-zinc-500 mt-1">
          BPMN files (.bpmn) or Mermaid files (.mmd, .mermaid)
        </p>
      </div>

      {/* Uploaded Files List */}
      {files.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-zinc-700">
            Uploaded Files ({files.length})
          </p>
          <div className="space-y-2">
            {files.map((uploadedFile, index) => (
              <Card key={index} className="p-3">
                <div className="flex items-center gap-3">
                  <FileText className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {uploadedFile.file.name}
                    </p>
                    <p className="text-xs text-zinc-500">
                      {uploadedFile.type === 'bpmn' ? 'BPMN File' : 'Mermaid File'} •{' '}
                      {(uploadedFile.file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeFile(index)}
                    className="h-8 w-8 p-0"
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
