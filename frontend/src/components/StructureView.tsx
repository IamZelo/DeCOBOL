import type { AstVariable, Finding, Job } from '../types'
import { findingsByRef, paragraphToMethodName, worstSeverity } from '../lib/structure'

function FindingNote({ findings }: { findings: Finding[] }) {
  if (findings.length === 0) return null
  const severity = worstSeverity(findings)
  return (
    <div className={`symbol-findings is-${severity}`}>
      {findings.map((f, i) => (
        <p className="symbol-finding-text" key={i}>
          {f.message}
        </p>
      ))}
    </div>
  )
}

function FieldRows({ variables, refs }: { variables: AstVariable[]; refs: Map<string, Finding[]> }) {
  const sorted = [...variables].sort((a, b) => a.source_line - b.source_line)
  return (
    <>
      {sorted.map((v) => {
        const findings = refs.get(v.name.toUpperCase()) ?? []
        const indent = Math.max(0, (v.level - 1)) * 10
        if (v.is_group) {
          return (
            <div className="symbol-row is-group" key={`${v.name}-${v.source_line}`} style={{ paddingLeft: indent }}>
              <span className="symbol-cobol">
                <span className="meta">{String(v.level).padStart(2, '0')}</span> {v.name}
              </span>
            </div>
          )
        }
        return (
          <div
            className={`symbol-row${findings.length ? ' has-findings' : ''}`}
            key={`${v.name}-${v.source_line}`}
            style={{ paddingLeft: indent }}
          >
            <span className="symbol-cobol">
              <span className="meta">{String(v.level).padStart(2, '0')}</span> {v.name}
              {v.pic ? <span className="meta symbol-pic"> PIC {v.pic}{v.usage !== 'DISPLAY' ? ` ${v.usage}` : ''}</span> : null}
            </span>
            <span className="symbol-arrow">→</span>
            <span className="symbol-java">
              <span className="symbol-java-type">{v.java_type}</span> {v.java_name}
            </span>
            <FindingNote findings={findings} />
          </div>
        )
      })}
    </>
  )
}

export function StructureView({ job, findings }: { job: Job; findings: Finding[] }) {
  const ast = job.result?.parsed_ast
  const documentation = job.result?.documentation
  const className = job.result?.class_name ?? 'Program'
  const refs = findingsByRef(findings)

  const variables: AstVariable[] =
    ast?.variables ??
    (documentation?.variable_map ?? []).map((m, i) => ({
      name: m.cobol_name,
      level: 1,
      parent: null,
      pic: m.pic,
      usage: m.usage,
      is_group: false,
      java_name: m.java_name,
      java_type: m.java_type,
      source_line: i,
    }))

  const paragraphs = [...(ast?.paragraphs ?? [])].sort((a, b) => a.start_line - b.start_line)

  return (
    <div className="structure">
      <header className="structure-class">
        <span className="structure-class-cobol">{ast?.program_id ?? job.filename}</span>
        <span className="symbol-arrow">→</span>
        <span className="structure-class-java">{className}.java</span>
      </header>

      <section className="structure-section">
        <header className="structure-section-head">
          <span className="findings-title">Fields</span>
          <span className="meta">{variables.filter((v) => !v.is_group).length} mapped</span>
        </header>
        {variables.length ? (
          <div className="symbol-list">
            <FieldRows variables={variables} refs={refs} />
          </div>
        ) : (
          <p className="meta">No data division fields parsed for this program.</p>
        )}
      </section>

      <section className="structure-section">
        <header className="structure-section-head">
          <span className="findings-title">Methods</span>
          <span className="meta">{paragraphs.length} paragraphs</span>
        </header>
        {paragraphs.length ? (
          <div className="symbol-list">
            {paragraphs.map((p) => {
              const pFindings = refs.get(p.name.toUpperCase()) ?? []
              return (
                <div className={`method-row${pFindings.length ? ' has-findings' : ''}`} key={p.name}>
                  <div className="method-row-head">
                    <span className="symbol-cobol">
                      {p.name}
                      {p.section ? <span className="meta"> · {p.section}</span> : null}
                    </span>
                    <span className="symbol-arrow">→</span>
                    <span className="symbol-java">{paragraphToMethodName(p.name)}()</span>
                    <span className="meta method-lines">
                      {Math.max(1, p.end_line - p.start_line + 1)} lines
                    </span>
                  </div>
                  {p.performs.length ? (
                    <div className="method-tags">
                      <span className="meta">performs</span>
                      {p.performs.map((call) => (
                        <span className="method-tag" key={call}>
                          {paragraphToMethodName(call)}()
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <FindingNote findings={pFindings} />
                </div>
              )
            })}
          </div>
        ) : (
          <p className="meta">No procedure division paragraphs parsed for this program.</p>
        )}
      </section>
    </div>
  )
}
