import { Button, Input, Label, TextField } from '@heroui/react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import type { Account } from './api.ts'
import { useAuth } from './auth.ts'

type SaveState = 'idle' | 'saving' | 'saved' | { error: string }

/** The candidate's details (FR-11): name, email, the role they are after and where they are. */
export function ProfilePage() {
  const { account, checking } = useAuth()

  return (
    <>
      <header className="app-header">
        <p className="eyebrow mb-2">Your account</p>
        <h1>
          Your <span className="text-success">profile</span>
        </h1>
        <p>A few details about you and the job you are after. None of them count in your scores.</p>
      </header>
      {checking ? (
        <p role="status" className="mt-8">
          Checking your session…
        </p>
      ) : account ? (
        <ProfileForm key={account.id} account={account} />
      ) : (
        <LoggedOut />
      )}
    </>
  )
}

function LoggedOut() {
  return (
    <section
      className="mt-8 rounded-[var(--radius)] border border-border bg-surface p-6"
      aria-labelledby="logged-out-title"
    >
      <h2 id="logged-out-title" className="m-0">
        You are not logged in
      </h2>
      <p className="mt-2 mb-4 text-muted">
        Log in to see your profile and keep your previous results on every device.
      </p>
      <Link to="/login" className="button button--primary font-semibold">
        Log in
      </Link>
    </section>
  )
}

function ProfileForm({ account }: { account: Account }) {
  const { logout, updateProfile } = useAuth()
  const [name, setName] = useState(account.name)
  const [targetRole, setTargetRole] = useState(account.target_role)
  const [location, setLocation] = useState(account.location)
  const [state, setState] = useState<SaveState>('idle')
  const changed =
    name !== account.name || targetRole !== account.target_role || location !== account.location

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setState('saving')
    try {
      await updateProfile({ name, target_role: targetRole, location })
      setState('saved')
    } catch (caught) {
      setState({
        error:
          caught instanceof Error ? caught.message : "We couldn't save your profile. Please try again.",
      })
    }
  }

  return (
    <form
      className="mt-8 grid gap-4 rounded-[var(--radius)] border border-border bg-surface p-6"
      aria-label="Profile"
      onSubmit={handleSubmit}
    >
      <div>
        <p className="eyebrow m-0">Email</p>
        <p className="m-0 mt-1 font-medium">{account.email}</p>
      </div>
      <TextField name="name" value={name} onChange={setName} isRequired fullWidth autoComplete="name">
        <Label>Name</Label>
        <Input />
      </TextField>
      <TextField name="target_role" value={targetRole} onChange={setTargetRole} fullWidth>
        <Label>Target role</Label>
        <Input placeholder="Data analyst" />
      </TextField>
      <TextField name="location" value={location} onChange={setLocation} fullWidth>
        <Label>Location</Label>
        <Input placeholder="Tashkent" />
      </TextField>

      {typeof state === 'object' && (
        <p className="message is-error" role="alert">
          {state.error}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          variant="primary"
          className="font-semibold"
          isDisabled={state === 'saving' || !changed}
        >
          {state === 'saving' ? 'Saving…' : 'Save'}
        </Button>
        {state === 'saved' && !changed && (
          <p role="status" className="m-0 text-sm text-success-soft-foreground">
            Saved.
          </p>
        )}
        <Button type="button" variant="secondary" className="ml-auto font-semibold" onPress={logout}>
          Log out
        </Button>
      </div>
    </form>
  )
}
