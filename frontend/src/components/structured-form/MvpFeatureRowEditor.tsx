import { Plus, Trash2 } from 'lucide-react';
import type { MvpFeatureRow } from '../../types/structuredForm';
import { EMPTY_MVP_ROW } from '../../utils/structuredFormTransform';

type MvpFeatureRowEditorProps = {
  rows: MvpFeatureRow[];
  onChange: (rows: MvpFeatureRow[]) => void;
  error?: string;
};

function inputClass(invalid?: boolean) {
  return `w-full rounded-lg border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 ${
    invalid
      ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
      : 'border-slate-300 focus:border-slate-500 focus:ring-slate-500'
  }`;
}

export default function MvpFeatureRowEditor({ rows, onChange, error }: MvpFeatureRowEditorProps) {
  const updateRow = (index: number, patch: Partial<MvpFeatureRow>) => {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const removeRow = (index: number) => {
    if (rows.length <= 1) {
      onChange([{ ...EMPTY_MVP_ROW }]);
      return;
    }
    onChange(rows.filter((_, i) => i !== index));
  };

  const addRow = () => {
    onChange([...rows, { ...EMPTY_MVP_ROW }]);
  };

  return (
    <div className="space-y-3">
      {rows.map((row, index) => (
        <div
          key={index}
          className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50/50 p-4 lg:grid-cols-[1fr_1fr_1fr_auto]"
        >
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">功能名称</label>
            <input
              className={inputClass(!!error)}
              value={row.name}
              onChange={(e) => updateRow(index, { name: e.target.value })}
              placeholder="例如：用户登录"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">功能描述</label>
            <input
              className={inputClass(!!error)}
              value={row.description}
              onChange={(e) => updateRow(index, { description: e.target.value })}
              placeholder="这个功能做什么"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">用户价值（可选）</label>
            <input
              className={inputClass()}
              value={row.user_value}
              onChange={(e) => updateRow(index, { user_value: e.target.value })}
              placeholder="为用户带来什么价值"
            />
          </div>
          <div className="flex items-end lg:pb-0.5">
            <button
              type="button"
              onClick={() => removeRow(index)}
              className="inline-flex items-center gap-1 rounded-md px-2 py-2 text-xs text-slate-500 hover:bg-slate-200 hover:text-red-600"
              title="删除此行"
            >
              <Trash2 className="h-4 w-4" />
              删除
            </button>
          </div>
        </div>
      ))}
      <button
        type="button"
        onClick={addRow}
        className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 hover:border-slate-400 hover:bg-slate-50"
      >
        <Plus className="h-4 w-4" />
        添加功能
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
