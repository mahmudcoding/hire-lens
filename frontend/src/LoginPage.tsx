import { Button, Input, Label, TextField } from '@heroui/react'
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { useAuth } from './auth.ts'

type Mode = 'login' | 'register'

/** Shortest password the API accepts; the field says so before the API has to. */
export const MIN_PASSWORD_LENGTH = 8

const switchLink =
  'cursor-pointer border-0 bg-transparent p-0 font-medium text-foreground underline underline-offset-2 hover:text-success-soft-foreground'

/** Log in or create an account (FR-11). */
export function LoginPage() {
  const { account, login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Already logged in, or just did: the profile is the place to be.
  useEffect(() => {
    if (account) navigate('/profile', { replace: true })
  }, [account, navigate])

  function switchMode(next: Mode) {
    setMode(next)
    setError(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(email, password, name)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const title = mode === 'login' ? 'Log in' : 'Create an account'

  return (
    <>
      <header className="app-header">
        <p className="eyebrow mb-2">Your account</p>
        <h1>
          {mode === 'login' ? (
            <>
              Welcome <span className="text-success">back</span>
            </>
          ) : (
            <>
              Create your <span className="text-success">account</span>
            </>
          )}
        </h1>
        <p>Keep your previous results and your profile on every device you use.</p>
      </header>

      <form
        className="mt-8 grid gap-4 rounded-[var(--radius)] border border-border bg-surface p-6"
        aria-label={title}
        onSubmit={handleSubmit}
      >
        {mode === 'register' && (
          <TextField name="name" value={name} onChange={setName} isRequired fullWidth autoComplete="name">
            <Label>Name</Label>
            <Input />
          </TextField>
        )}
        <TextField
          name="email"
          type="email"
          value={email}
          onChange={setEmail}
          isRequired
          fullWidth
          autoComplete="email"
        >
          <Label>Email</Label>
          <Input />
        </TextField>
        <TextField
          name="password"
          type="password"
          value={password}
          onChange={setPassword}
          isRequired
          fullWidth
          minLength={mode === 'register' ? MIN_PASSWORD_LENGTH : undefined}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
        >
          <Label>Password</Label>
          <Input />
          {mode === 'register' && (
            <p className="m-0 text-sm text-muted">At least {MIN_PASSWORD_LENGTH} characters.</p>
          )}
        </TextField>

        {error && (
          <p className="message is-error" role="alert">
            {error}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" variant="primary" className="font-semibold" isDisabled={busy}>
            {busy ? 'One moment…' : title}
          </Button>
          <p className="m-0 text-sm text-muted">
            {mode === 'login' ? (
              <>
                New here?{' '}
                <button type="button" className={switchLink} onClick={() => switchMode('register')}>
                  Create an account
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button type="button" className={switchLink} onClick={() => switchMode('login')}>
                  Log in
                </button>
              </>
            )}
          </p>
        </div>
      </form>
    </>
  )
}
