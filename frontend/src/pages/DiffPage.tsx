import { useState } from 'react'
import { DiffView } from '../components/DiffView'
import { TopNav } from '../components/TopNav'
import { ValidationReport } from '../components/ValidationReport'
import {
  DIFF_COBOL,
  DIFF_FINDINGS,
  DIFF_JAVA,
  DIFF_META,
} from '../data/fixtures'

export function DiffPage() {
  const [mode, setMode] = useState<'split' | 'unified'>('split')

  return (
    <div className="app">
      <TopNav
        right={
          <>
            <span>Output:</span>
            <span className="path-accent">{DIFF_META.output_path}</span>
            <span>(on disk)</span>
          </>
        }
      />

      <div className="page is-wide">
        <div className="page-inner is-wide">
          <div className="diff-toolbar">
            <div className="segmented">
              <button
                className={mode === 'split' ? 'is-on' : ''}
                onClick={() => setMode('split')}
              >
                SPLIT
              </button>
              <button
                className={mode === 'unified' ? 'is-on' : ''}
                onClick={() => setMode('unified')}
              >
                UNIFIED
              </button>
            </div>
            <button className="btn btn-round">Open in IDE</button>
            <button className="btn-primary btn-compact">Re-run</button>
          </div>

          <DiffView
            mode={mode}
            source={{ ...DIFF_META.source, rows: DIFF_COBOL }}
            target={{ ...DIFF_META.target, rows: DIFF_JAVA }}
          />

          <ValidationReport
            findings={DIFF_FINDINGS}
            equivalence={DIFF_META.equivalence}
          />
        </div>
      </div>
    </div>
  )
}
