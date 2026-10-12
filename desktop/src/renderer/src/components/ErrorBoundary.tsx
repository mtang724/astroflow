import { Component, type ErrorInfo, type ReactNode } from 'react'
import { TriangleAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Props {
  children: ReactNode
  /** Changing it resets the boundary (e.g. the selected target). */
  resetKey?: unknown
}

interface State {
  error: Error | null
  key: unknown
}

/** Keeps one broken panel from taking the whole window down (React unmounts the tree on an uncaught error). */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, key: this.props.resetKey }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    return props.resetKey !== state.key ? { error: null, key: props.resetKey } : null
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('UI error', error, info.componentStack)
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-md text-center">
          <TriangleAlert className="mx-auto mb-3 size-8 text-warn" />
          <p className="text-sm font-medium">这个面板出错了</p>
          <p className="mt-1 font-mono text-xs break-all text-muted-foreground">{this.state.error.message}</p>
          <Button variant="secondary" size="sm" className="mt-4" onClick={() => this.setState({ error: null })}>
            重试
          </Button>
        </div>
      </div>
    )
  }
}
