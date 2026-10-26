import type { ChangeEvent } from 'react'
import './ConsentNotice.css'

type Props = {
  checked: boolean
  onChange: (checked: boolean) => void
}

// NFR-03 / DP-30: a candidate has to see this and tick the box before HireLens
// will touch their resume. The wording describes only what the product
// actually does; it still needs a legal review against Uzbekistan's personal
// data law before this goes live (tracked on DP-30).
export function ConsentNotice({ checked, onChange }: Props) {
  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onChange(event.target.checked)
  }

  return (
    <section className="consent" aria-labelledby="consent-title">
      <h2 id="consent-title">Your privacy</h2>
      <p id="consent-notice-text">
        HireLens stores your resume only to generate the results below. It is kept for up to 24
        hours and then deleted automatically, together with the text read from it, and is never
        shared with anyone else.
      </p>
      <label className="consent-checkbox">
        <input
          type="checkbox"
          checked={checked}
          onChange={handleChange}
          aria-describedby="consent-notice-text"
        />
        I have read the privacy notice and agree to HireLens storing and processing my resume as
        described above.
      </label>
    </section>
  )
}
