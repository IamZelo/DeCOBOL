import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { getFsFile, getFsTree } from '../api/client'
import type { FsEntry } from '../types'

export interface TreeNode {
  name: string
  path: string
  type: 'file' | 'dir'
  size?: number
  /** Only meaningful for dirs. undefined = not fetched yet. */
  children?: TreeNode[]
  expanded?: boolean
  loading?: boolean
}

function toNodes(parentPath: string, entries: FsEntry[]): TreeNode[] {
  return entries.map((e) => ({
    name: e.name,
    path: parentPath ? `${parentPath}/${e.name}` : e.name,
    type: e.type,
    size: e.size,
  }))
}

function updateNode(
  nodes: TreeNode[],
  path: string,
  patch: Partial<TreeNode>,
): TreeNode[] {
  return nodes.map((n) => {
    if (n.path === path) return { ...n, ...patch }
    if (n.children && path.startsWith(`${n.path}/`)) {
      return { ...n, children: updateNode(n.children, path, patch) }
    }
    return n
  })
}

interface WorkspaceState {
  root: string | null
  tree: TreeNode[]
  loading: boolean
  error: string | null
  selected: string[]
  activePath: string | null
  activeContent: string | null
  activeLoading: boolean
  activeError: string | null
  toggleDir: (path: string) => void
  toggleSelected: (path: string) => void
  setActivePath: (path: string) => void
  clearSelection: () => void
  selectAllFiles: () => void
  reload: () => void
  findNode: (path: string) => TreeNode | undefined
}

const Ctx = createContext<WorkspaceState | null>(null)

function collectAllFilePaths(nodes: TreeNode[]): string[] {
  const out: string[] = []
  for (const n of nodes) {
    if (n.type === 'file') out.push(n.path)
    else if (n.children) out.push(...collectAllFilePaths(n.children))
  }
  return out
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [root, setRoot] = useState<string | null>(null)
  const [tree, setTree] = useState<TreeNode[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [activePath, setActivePathState] = useState<string | null>(null)
  const [activeContent, setActiveContent] = useState<string | null>(null)
  const [activeLoading, setActiveLoading] = useState(false)
  const [activeError, setActiveError] = useState<string | null>(null)
  const [reloadTick, setReloadTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getFsTree('', 'input')
      .then((t) => {
        if (cancelled) return
        setRoot(t.root)
        const nodes = toNodes('', t.entries)
        setTree(nodes)
        const firstFile = nodes.find((n) => n.type === 'file')
        if (firstFile) {
          setActivePathState(firstFile.path)
          setSelected([firstFile.path])
        }
      })
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [reloadTick])

  useEffect(() => {
    if (!activePath) return
    let cancelled = false
    setActiveLoading(true)
    setActiveError(null)
    getFsFile(activePath, 'input')
      .then((f) => !cancelled && setActiveContent(f.content))
      .catch((err) => !cancelled && setActiveError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setActiveLoading(false))
    return () => {
      cancelled = true
    }
  }, [activePath])

  const toggleDir = useCallback((path: string) => {
    setTree((prev) => {
      const find = (nodes: TreeNode[]): TreeNode | undefined => {
        for (const n of nodes) {
          if (n.path === path) return n
          if (n.children) {
            const hit = find(n.children)
            if (hit) return hit
          }
        }
        return undefined
      }
      const node = find(prev)
      if (!node) return prev

      if (node.children) {
        return updateNode(prev, path, { expanded: !node.expanded })
      }

      // Not loaded yet — fetch, then expand.
      updateNode(prev, path, { loading: true })
      getFsTree(path, 'input')
        .then((t) => {
          setTree((cur) =>
            updateNode(cur, path, {
              children: toNodes(path, t.entries),
              expanded: true,
              loading: false,
            }),
          )
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : String(err))
          setTree((cur) => updateNode(cur, path, { loading: false }))
        })
      return updateNode(prev, path, { loading: true })
    })
  }, [])

  const toggleSelected = useCallback((path: string) => {
    setSelected((prev) =>
      prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path],
    )
  }, [])

  const setActivePath = useCallback((path: string) => setActivePathState(path), [])
  const clearSelection = useCallback(() => setSelected([]), [])
  const selectAllFiles = useCallback(
    () => setSelected(collectAllFilePaths(tree)),
    [tree],
  )
  const reload = useCallback(() => setReloadTick((t) => t + 1), [])

  const findNode = useCallback(
    (path: string): TreeNode | undefined => {
      const search = (nodes: TreeNode[]): TreeNode | undefined => {
        for (const n of nodes) {
          if (n.path === path) return n
          if (n.children) {
            const hit = search(n.children)
            if (hit) return hit
          }
        }
        return undefined
      }
      return search(tree)
    },
    [tree],
  )

  const value: WorkspaceState = {
    root,
    tree,
    loading,
    error,
    selected,
    activePath,
    activeContent,
    activeLoading,
    activeError,
    toggleDir,
    toggleSelected,
    setActivePath,
    clearSelection,
    selectAllFiles,
    reload,
    findNode,
  }

  return createElement(Ctx.Provider, { value }, children)
}

export function useWorkspace() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useWorkspace must be used inside WorkspaceProvider')
  return ctx
}
