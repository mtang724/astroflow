import { Fragment, useEffect } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useLanguageFromSettings, useLiveEvents, useUpdateChecks } from '@/api/hooks'
import { TopBar } from '@/features/layout/TopBar'
import { Sidebar } from '@/features/layout/Sidebar'
import { JobsPanel } from '@/features/jobs/JobsPanel'
import { TargetView } from '@/features/target/TargetView'
import { Welcome } from '@/features/layout/Welcome'
import { SettingsDialog } from '@/features/settings/SettingsDialog'
import { SetupDialog } from '@/features/setup/SetupDialog'
import { ImportDialog } from '@/features/import/ImportDialog'
import { ImageViewer } from '@/features/viewer/ImageViewer'
import { BatchDialog } from '@/features/batch/BatchDialog'
import { ShareDialog } from '@/features/share/ShareDialog'
import { StorageDialog } from '@/features/storage/StorageDialog'
import { ArchiveDialog } from '@/features/target/ArchiveDialog'
import { UpdateDialog } from '@/features/updates/UpdateDialog'
import { onShowTarget } from '@/lib/desktop'
import { useLanguage } from '@/lib/i18n'
import { useUi } from '@/state/ui'

export function App(): React.JSX.Element {
  useLiveEvents()
  useLanguageFromSettings()
  useUpdateChecks()
  const language = useLanguage((s) => s.language)
  const selected = useUi((s) => s.selected)
  // a notification was clicked: show the target it was about
  useEffect(() => onShowTarget((target) => useUi.getState().select(target)), [])
  return (
    // keyed by the language: every text is drawn again in the new one (what is open stays open: it lives in useUi)
    <Fragment key={language}>
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
          <SetupDialog />
          <ImportDialog />
          <BatchDialog />
          <StorageDialog />
          <ArchiveDialog />
          <ShareDialog />
          <UpdateDialog />
          <ImageViewer />
        </ErrorBoundary>
      </TooltipProvider>
    </Fragment>
  )
}
