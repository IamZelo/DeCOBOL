import { PIPELINE_STEPS } from '../data/fixtures'

export type StepState = 'done' | 'active' | 'pending'

function Check() {
  return (
    <svg viewBox="0 0 8 8" width="8" height="8" aria-hidden="true">
      <path
        d="M.8 4.2 3 6.4 7.2 1.4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.1"
      />
    </svg>
  )
}

/** The five-agent horizontal step strip. */
export function WorkflowGraph({
  states,
}: {
  states: Record<string, StepState>
}) {
  return (
    <div className="steps">
      {PIPELINE_STEPS.map((step) => {
        const state = states[step.agent] ?? 'pending'
        return (
          <div className={`step is-${state}`} key={step.index}>
            <div className="step-head">
              <span className="step-name">
                {step.index} {step.agent}
              </span>
              {state === 'done' ? (
                <span className="step-check">
                  <Check />
                </span>
              ) : state === 'active' ? (
                <span className="step-pip" />
              ) : (
                <span className="step-name">·</span>
              )}
            </div>
            <div className="step-tool">{step.tool}</div>
            <div className="step-detail">
              {step.detail}
              {state === 'active' ? <span className="caret" /> : null}
            </div>
          </div>
        )
      })}
    </div>
  )
}
