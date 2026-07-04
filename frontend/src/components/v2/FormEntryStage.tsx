import type { FormSubView } from '../../services/sessionService';
import { V2_PAGE_CLASS } from '../../constants/v2Layout';
import ProjectEntryChooser from '../project-entry/ProjectEntryChooser';
import ImportPrdPanel from '../project-entry/ImportPrdPanel';
import ImportPromptsPanel from '../project-entry/ImportPromptsPanel';
import StructuredRequirementsForm, {
  type StructuredRequirementsFormProps,
} from './StructuredRequirementsForm';

export type FormEntryStageProps = {
  formSubView: FormSubView;
  manualPrdInput: string;
  manualApiDocsInput: string;
  actionLocked: boolean;
  onSelectStructured: () => void;
  onSelectImportPrd: () => void;
  onSelectImportPrompts: () => void;
  onManualPrdInputChange: (value: string) => void;
  onManualApiDocsInputChange: (value: string) => void;
  onEnterPrdReview: () => void;
  onStartApiDocs: () => void;
  onEnterPromptsStage: () => void;
  onStartPrompts: () => void;
  onBackToChooser: () => void;
  structuredFormProps: StructuredRequirementsFormProps;
};

export default function FormEntryStage({
  formSubView,
  manualPrdInput,
  manualApiDocsInput,
  actionLocked,
  onSelectStructured,
  onSelectImportPrd,
  onSelectImportPrompts,
  onManualPrdInputChange,
  onManualApiDocsInputChange,
  onEnterPrdReview,
  onStartApiDocs,
  onEnterPromptsStage,
  onStartPrompts,
  onBackToChooser,
  structuredFormProps,
}: FormEntryStageProps) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <main className={`${V2_PAGE_CLASS} py-8`}>
        {formSubView === 'chooser' && (
          <ProjectEntryChooser
            onSelectStructured={onSelectStructured}
            onSelectImportPrd={onSelectImportPrd}
            onSelectImportPrompts={onSelectImportPrompts}
          />
        )}

        {formSubView === 'structured' && (
          <StructuredRequirementsForm {...structuredFormProps} />
        )}

        {formSubView === 'import-prd' && (
          <ImportPrdPanel
            manualPrdInput={manualPrdInput}
            onManualPrdInputChange={onManualPrdInputChange}
            onEnterPrdReview={onEnterPrdReview}
            onStartApiDocs={onStartApiDocs}
            onBack={onBackToChooser}
            actionLocked={actionLocked}
          />
        )}

        {formSubView === 'import-prompts' && (
          <ImportPromptsPanel
            manualPrdInput={manualPrdInput}
            manualApiDocsInput={manualApiDocsInput}
            onManualPrdInputChange={onManualPrdInputChange}
            onManualApiDocsInputChange={onManualApiDocsInputChange}
            onEnterStage={onEnterPromptsStage}
            onStartPrompts={onStartPrompts}
            onBack={onBackToChooser}
            actionLocked={actionLocked}
          />
        )}
      </main>
    </div>
  );
}
