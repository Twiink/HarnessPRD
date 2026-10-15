import { Plus, Trash2 } from 'lucide-react';
import type { UiPageRow } from '../../types/structuredForm';
import { EMPTY_UI_PAGE_ROW } from '../../utils/structuredFormTransform';

type UiPageRowEditorProps = {
  rows: UiPageRow[];
  onChange: (rows: UiPageRow[]) => void;
  error?: string;
};

function inputClass(invalid?: boolean) {
  return `w-full rounded border bg-white px-3 py-2 text-sm text-ink placeholder:text-slate-400 focus:outline-none focus:ring-1 ${
    invalid
      ? 'border-mark/60 focus:border-mark focus:ring-mark'
      : 'border-slate-300 focus:border-primary-600 focus:ring-primary-600'
  }`;
}

export default function UiPageRowEditor({ rows, onChange, error }: UiPageRowEditorProps) {
  const updateRow = (index: number, patch: Partial<UiPageRow>) => {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const removeRow = (index: number) => {
    if (rows.length <= 1) {
      onChange([{ ...EMPTY_UI_PAGE_ROW }]);
      return;
    }
    onChange(rows.filter((_, i) => i !== index));
  };

  const addRow = () => {
    onChange([...rows, { ...EMPTY_UI_PAGE_ROW }]);
  };

  return (
    <div className="space-y-3">
      {rows.map((row, index) => (
        <div
          key={index}
          className="grid gap-3 border-t border-hair pt-3 first:border-t-0 first:pt-0 lg:grid-cols-[1fr_1fr_1fr_auto]"
        >
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">页面名称</label>
            <input
              className={inputClass(!!error)}
              value={row.name}
              onChange={(e) => updateRow(index, { name: e.target.value })}
              placeholder="例如：首页"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">主要模块</label>
            <input
              className={inputClass()}
              value={row.modules}
              onChange={(e) => updateRow(index, { modules: e.target.value })}
              placeholder="逗号分隔，如：登录表单, 验证码"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">备注（可选）</label>
            <input
              className={inputClass()}
              value={row.notes}
              onChange={(e) => updateRow(index, { notes: e.target.value })}
              placeholder="页面用途说明"
            />
          </div>
          <div className="flex items-end lg:pb-0.5">
            <button
              type="button"
              onClick={() => removeRow(index)}
              className="inline-flex items-center gap-1 rounded px-2 py-2 text-xs text-slate-500 hover:bg-slate-100 hover:text-mark"
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
        className="inline-flex items-center gap-1.5 rounded border border-dashed border-slate-400 px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-primary-600 hover:text-primary-700"
      >
        <Plus className="h-4 w-4" />
        添加页面
      </button>
      {error && <p className="text-sm text-mark">{error}</p>}
    </div>
  );
}
