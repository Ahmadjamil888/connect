import { RedirectToSignIn, SignInButton, SignUpButton, useAuth, useUser } from '@clerk/react'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

type BridgeState = 'idle' | 'posting' | 'success' | 'error'

export function AuthCliPage() {
  const [searchParams] = useSearchParams()
  const { isSignedIn, getToken } = useAuth()
  const { user } = useUser()
  const callbackUrl = searchParams.get('callback') || ''
  const [bridgeState, setBridgeState] = useState<BridgeState>('idle')
  const [message, setMessage] = useState('Sign in with Clerk to finish the CONNECT CLI handoff.')
  const returnUrl = typeof window !== 'undefined' ? window.location.href : '/auth/cli'

  const callbackOriginOk = useMemo(() => {
    if (!callbackUrl) return false
    try {
      const parsed = new URL(callbackUrl)
      return parsed.protocol === 'http:' && parsed.hostname === '127.0.0.1'
    } catch {
      return false
    }
  }, [callbackUrl])

  useEffect(() => {
    async function bridge() {
      if (!isSignedIn || !callbackOriginOk || bridgeState === 'posting' || bridgeState === 'success') {
        return
      }
      try {
        setBridgeState('posting')
        setMessage('Completing secure handoff to your local CONNECT CLI...')
        const token = await getToken()
        if (!token) {
          throw new Error('Clerk token is unavailable for this session.')
        }
        const response = await fetch(callbackUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            token,
            email: user?.primaryEmailAddress?.emailAddress || '',
          }),
        })
        const payload = await response.json()
        if (!response.ok || !payload.ok) {
          throw new Error(payload.error || 'CLI callback rejected the sign-in.')
        }
        setBridgeState('success')
        setMessage('Signed in successfully. You can return to the CONNECT CLI.')
      } catch (error) {
        setBridgeState('error')
        setMessage(error instanceof Error ? error.message : 'Sign-in handoff failed.')
      }
    }

    bridge()
  }, [bridgeState, callbackOriginOk, callbackUrl, getToken, isSignedIn, user])

  if (!isSignedIn && callbackOriginOk) {
    return (
      <>
        <RedirectToSignIn signInForceRedirectUrl={returnUrl} signInFallbackRedirectUrl={returnUrl} />
        <main className="min-h-screen bg-black px-5 py-16">
          <div className="mx-auto max-w-3xl rounded-[2rem] border border-white/8 bg-[#0a0d0c] p-8 text-center">
            <div className="text-xs uppercase tracking-[0.22em] text-[#27F3A9]">CLI Sign-In</div>
            <h1 className="mt-4 text-4xl font-light tracking-[-0.04em] text-white md:text-5xl">
              Redirecting to Clerk sign-in.
            </h1>
            <p className="mt-5 text-base leading-7 text-neutral-400">
              If the redirect does not start automatically, use the sign-in button below.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <SignInButton mode="redirect" forceRedirectUrl={returnUrl} fallbackRedirectUrl={returnUrl}>
                <button className="rounded-full border border-white/10 px-5 py-3 text-sm text-white transition hover:border-[#27F3A9]/50">
                  Continue to sign in
                </button>
              </SignInButton>
              <SignUpButton mode="redirect" forceRedirectUrl={returnUrl} fallbackRedirectUrl={returnUrl}>
                <button className="rounded-full bg-[#27F3A9] px-5 py-3 text-sm font-medium text-black transition hover:brightness-110">
                  Create account
                </button>
              </SignUpButton>
            </div>
          </div>
        </main>
      </>
    )
  }

  return (
    <main className="min-h-[calc(100vh-81px)] bg-black px-5 py-16">
      <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="rounded-[2rem] border border-white/8 bg-[#060606] p-8">
          <div className="text-xs uppercase tracking-[0.22em] text-[#27F3A9]">CLI Sign-In</div>
          <h1 className="mt-4 max-w-xl text-4xl font-light tracking-[-0.04em] text-white md:text-6xl">
            Authenticate once. Return to the terminal already signed in.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-neutral-400">
            CONNECT opens this page from the CLI, waits on a localhost callback, and stores the validated Clerk session on the backend only after the token is verified.
          </p>
          <div className="mt-8 grid gap-3 text-sm text-neutral-300">
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">Origin: {searchParams.get('origin') || 'browser'}</div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 break-all">
              Callback: {callbackUrl || 'missing'}
            </div>
          </div>
        </section>

        <section className="rounded-[2rem] border border-white/8 bg-[#0a0d0c] p-8">
          <div className="text-xs uppercase tracking-[0.22em] text-neutral-500">Status</div>
          <div className="mt-4 rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-6">
            <div
              className={`text-sm uppercase tracking-[0.18em] ${
                bridgeState === 'success'
                  ? 'text-[#27F3A9]'
                  : bridgeState === 'error'
                    ? 'text-[#ff8b8b]'
                    : 'text-neutral-500'
              }`}
            >
              {bridgeState}
            </div>
            <p className="mt-4 text-base leading-7 text-neutral-300">{message}</p>
          </div>

          {!isSignedIn ? (
            <div className="mt-6 flex flex-wrap gap-3">
              <SignInButton mode="redirect" forceRedirectUrl={returnUrl} fallbackRedirectUrl={returnUrl}>
                <button className="rounded-full border border-white/10 px-5 py-3 text-sm text-white transition hover:border-[#27F3A9]/50">
                  Sign in
                </button>
              </SignInButton>
              <SignUpButton mode="redirect" forceRedirectUrl={returnUrl} fallbackRedirectUrl={returnUrl}>
                <button className="rounded-full bg-[#27F3A9] px-5 py-3 text-sm font-medium text-black transition hover:brightness-110">
                  Create account
                </button>
              </SignUpButton>
            </div>
          ) : (
            <div className="mt-6 rounded-[1.5rem] border border-[#27F3A9]/18 bg-[#08110d] p-5 text-sm leading-7 text-neutral-300">
              Signed in as {user?.primaryEmailAddress?.emailAddress || user?.id}.
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
