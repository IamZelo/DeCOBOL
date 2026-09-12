import { Link } from 'react-router-dom'
import { ThemeToggle } from '../components/ThemeToggle'
import {
  IconCode,
  IconCpu,
  IconFile,
  IconLayers,
  IconShield,
  IconTerminal,
} from '../components/icons'
import { useWorkspace } from '../hooks/useWorkspace'

/** The default INPUT_ROOT (backend/app/config.py) when no .env override is set. */
function isDefaultInput(root: string) {
  return root.replace(/\\/g, '/').endsWith('examples/lendwise')
}

const TRAP_ROWS: {
  cobol: string
  cobolNote: string
  naive: string
  naiveNote: string
  correct: string
  correctNote: string
}[] = [
  {
    cobol: 'MOVE "HELLO" TO X',
    cobolNote: 'where X PIC X(10)',
    naive: 'x = "HELLO"',
    naiveNote: 'missing padding',
    correct: 'x = "HELLO     "',
    correctNote: 'right-padded to 10',
  },
  {
    cobol: 'PIC S9(15)V9(2)',
    cobolNote: '(money, COMP-3)',
    naive: 'double',
    naiveNote: 'precision loss risk',
    correct: 'BigDecimal',
    correctNote: 'scale 2',
  },
  {
    cobol: 'COMPUTE X ROUNDED',
    cobolNote: '= …',
    naive: '// default rounding',
    naiveNote: 'unspecified mode',
    correct: 'RoundingMode.HALF_UP',
    correctNote: 'explicit .setScale()',
  },
  {
    cobol: 'MOVE 12345 TO Y',
    cobolNote: 'where Y PIC 9(3)',
    naive: 'y = 12345',
    naiveNote: 'overflow, no truncation',
    correct: 'y = 345',
    correctNote: 'high-order truncation',
  },
]

const AGENTS: {
  icon: () => JSX.Element
  name: string
  detail: string
}[] = [
  { icon: IconTerminal, name: 'Parser', detail: 'Reads the data division precisely; procedure division carried through verbatim.' },
  { icon: IconCode, name: 'Converter', detail: 'Drafts Java from the AST via the local LLM, with a deterministic Jinja fallback.' },
  { icon: IconCpu, name: 'Optimizer', detail: 'Cleans up the generated code without touching core logic.' },
  { icon: IconShield, name: 'Validator', detail: 'Runs javac and semantic checks; drives the retry loop back to Converter.' },
  { icon: IconLayers, name: 'Documenter', detail: 'Generates Javadoc and the field-by-field variable map.' },
]

export function LandingPage() {
  const { root, error: workspaceError } = useWorkspace()

  return (
    <div className="landing">
      <header className="landing-header">
        <Link to="/" className="nav-word">DeCOBOL</Link>
        <div className="landing-header-actions">
          <ThemeToggle />
          <Link to="/workspace" className="btn-primary btn-compact">
            Launch Workspace
          </Link>
        </div>
      </header>

      <section className="landing-hero is-centered">
        <h1 className="display-1">Agentic COBOL → Java modernization.</h1>
        <p className="landing-lead is-centered">
          DeCOBOL converts legacy COBOL into compilable, idiomatic Java 21 —
          preserving mainframe arithmetic exactly, catching its own mistakes,
          and retrying itself before you ever see the output. Every run stays
          on your machine.
        </p>
        <div className="landing-cta-row is-centered">
          <Link to="/workspace" className="btn-primary">
            Launch Workspace
            <span className="btn-key">↵</span>
          </Link>
        </div>
        <p className="landing-footnote is-centered">
          No sign-up. Runs against your own local model.
        </p>
        {workspaceError ? (
          <p className="landing-input-note is-centered is-warning">
            Can&rsquo;t reach the backend to read the input directory. Start it,
            then set <code>INPUT_ROOT</code> and <code>OUTPUT_ROOT</code> in
            your <code>.env</code> before launching.
          </p>
        ) : root ? isDefaultInput(root) ? (
          <p className="landing-input-note is-centered is-warning">
            Using the bundled sample input (<code>examples/lendwise</code>).
            Set <code>INPUT_ROOT</code> and <code>OUTPUT_ROOT</code> in your{' '}
            <code>.env</code> to point at your own COBOL project.
          </p>
        ) : (
          <p className="landing-input-note is-centered">
            Input directory: <code>{root}</code>
          </p>
        ) : null}
      </section>

      <section className="landing-section">
        <div className="landing-section-head">
          <span className="label">The COBOL problem</span>
          <h2 className="display-2">More than just translation.</h2>
          <p className="landing-lead">
            Trillions of dollars of business logic still runs on COBOL. Asking
            a general-purpose LLM to &ldquo;convert this to Java&rdquo; gives
            code that <span className="hl">compiles</span> but often{' '}
            <span className="hl">behaves differently</span>. COBOL semantics
            are counterintuitive — our edge is domain knowledge and
            deterministic validation, not a bigger model.
          </p>
        </div>

        <div className="trap-table-wrap">
          <table className="trap-table">
            <thead>
              <tr>
                <th>COBOL Behavior</th>
                <th>Naive Java Translation</th>
                <th>DeCOBOL Correct Translation</th>
              </tr>
            </thead>
            <tbody>
              {TRAP_ROWS.map((r) => (
                <tr key={r.cobol}>
                  <td>
                    <code className="is-cobol-code">{r.cobol}</code>
                    <span className="meta">{r.cobolNote}</span>
                  </td>
                  <td>
                    <span className="trap-cell is-wrong">
                      <span className="trap-mark">✕</span>
                      <code>{r.naive}</code>
                    </span>
                    <span className="meta">{r.naiveNote}</span>
                  </td>
                  <td>
                    <span className="trap-cell is-right">
                      <span className="trap-mark">✓</span>
                      <code>{r.correct}</code>
                    </span>
                    <span className="meta">{r.correctNote}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="landing-section">
        <div className="landing-section-head">
          <span className="label">How it works</span>
          <h2 className="display-2">Agentic architecture.</h2>
          <p className="landing-lead">
            A state graph coordinates five agents. The LLM decides; deterministic
            code does the work. Every step emits an event, and a validation
            failure loops back to the Converter — not to you.
          </p>
        </div>

        <div className="agent-cards">
          {AGENTS.map((a, i) => {
            const Icon = a.icon
            return (
              <div className="agent-card-wrap" key={a.name}>
                <div className="agent-card">
                  <span className="agent-card-icon">
                    <Icon />
                  </span>
                  <b>{a.name}</b>
                  <p className="meta">{a.detail}</p>
                </div>
                {i < AGENTS.length - 1 ? <span className="agent-card-arrow">→</span> : null}
              </div>
            )
          })}
        </div>
      </section>

      <section className="landing-section">
        <div className="landing-section-head">
          <span className="label">Under the hood</span>
          <h2 className="display-2">Built on solid foundations.</h2>
        </div>

        <div className="foundation-grid">
          <div className="foundation-card">
            <div className="foundation-card-head">
              <IconCpu />
              <b>Local LLM runtime</b>
            </div>
            <ul>
              <li><b>llama.cpp:</b> serves an OpenAI-compatible API entirely offline via llama-server.</li>
              <li><b>Model:</b> a 7B-class coder model (e.g. Qwen2.5-Coder-7B-Instruct) in GGUF format.</li>
              <li><b>Fallback:</b> MOCK_LLM=true runs the whole pipeline offline on deterministic logic if the model is down.</li>
            </ul>
          </div>
          <div className="foundation-card">
            <div className="foundation-card-head">
              <IconFile />
              <b>Backend &amp; interface</b>
            </div>
            <ul>
              <li><b>Flask API:</b> REST endpoints plus Server-Sent Events for live agent progress.</li>
              <li><b>LangGraph:</b> manages the state graph, conditional routing, and the retry loop.</li>
              <li><b>React + Vite:</b> a workspace UI with a live structure view, dependency graph, and SSE-driven pipeline tracking.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="landing-section landing-cost">
        <div className="landing-section-head">
          <span className="label">The cost argument</span>
          <h2 className="display-2">Most agents pay for the loop per file. DeCOBOL doesn&rsquo;t.</h2>
        </div>
        <div className="cost-stats">
          <div className="cost-stat">
            <span className="cost-stat-value">1</span>
            <span className="meta">
              LLM call per file — parsing, type-mapping, compilation, and
              semantic validation are deterministic Python, not model calls.
            </span>
          </div>
          <div className="cost-stat">
            <span className="cost-stat-value">5–10</span>
            <span className="meta">
              LLM turns a general coding agent spends per file — generate,
              compile, see the error, retry — resending growing context each
              time.
            </span>
          </div>
        </div>
      </section>

      <section className="landing-final">
        <h2 className="display-2">Bring your own COBOL.</h2>
        <Link to="/workspace" className="btn-primary">
          Launch Workspace
          <span className="btn-key">↵</span>
        </Link>
      </section>

      <footer className="landing-footer">
        <span className="meta">
          DeCOBOL — built in 36 hours by five engineers who got tired of
          reading fixed-column COBOL by hand.
        </span>
      </footer>
    </div>
  )
}
