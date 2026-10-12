import { TooltipProvider } from '@/components/ui/tooltip'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useLiveEvents } from '@/api/hooks'
import { TopBar } from '@/features/layout/TopBar'
import { Sidebar } from '@/features/layout/Sidebar'
import { JobsPanel } from '@/features/jobs/JobsPanel'
import { TargetView } from '@/features/target/TargetView'
import { Welcome } from '@/features/layout/Welcome'
import { SettingsDialog } from '@/features/settings/SettingsDialog'
import { ImportDialog } from '@/features/import/ImportDialog'
import { ImageViewer } from '@/features/viewer/ImageViewer'
import { useUi } from '@/state/ui'

export function App(): React.JSX.Element {
  useLiveEvents()
  const selected = useUi((s) => s.selected)
  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-full flex-col">
        <TopBar />
        <div className="flex min-h-0 flex-1">
          <Sidebar />
          <main className="min-w-0 flex-1">
            <ErrorBoundary resetKey={selected}>
              {selected ? <TargetView key={selected} path={selected} /> : <Welcome />}
            </ErrorBoundary>
          </main>
        </div>
        <ErrorBoundary>
          <JobsPanel />
        </ErrorBoundary>
      </div>
      <ErrorBoundary>
        <SettingsDialog />
        <ImportDialog />
        <ImageViewer />
      </ErrorBoundary>
    </TooltipProvider>
  )
}
