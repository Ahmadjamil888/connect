import { useEffect, useRef, type ReactNode } from 'react'

const VIDEO_HUMAN =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260424_090051_64ea5059-da6b-492b-a171-aa7ecc767dc3.mp4'
const VIDEO_AI =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260424_093237_ff0ddc63-c068-4e29-96da-fdd0e40af133.mp4'

type VideoIconProps = {
  src: string
  size?: number
}

function VideoIcon({ src, size = 72 }: VideoIconProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null)

  useEffect(() => {
    videoRef.current?.play().catch(() => {})
  }, [])

  return (
    <span
      className="inline-block align-middle rounded-full overflow-hidden"
      style={{
        width: `clamp(48px, 10vw, ${size}px)`,
        height: `clamp(48px, 10vw, ${size}px)`,
        flexShrink: 0,
      }}
    >
      <video
        ref={videoRef}
        autoPlay
        loop
        muted
        playsInline
        src={src}
        style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
      />
    </span>
  )
}

function GradientLine({ children }: { children: ReactNode }) {
  return (
    <span
      style={{
        display: 'block',
        lineHeight: 1.1,
        marginBottom: '-0.22em',
        background: 'linear-gradient(90deg, #333333 0%, #878787 50%, #333333 100%)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
      }}
    >
      {children}
    </span>
  )
}

export default function HeroSection() {
  return (
    <section
      className="relative overflow-hidden flex flex-col items-center justify-center"
      style={{ height: '100vh', background: '#000' }}
    >
      <div className="relative z-10 flex flex-col items-center text-center px-4 max-w-5xl mx-auto">
        <h1
          style={{
            fontFamily: "'YDYoonche L', 'YDYoonche M', sans-serif",
            fontWeight: 300,
            letterSpacing: '-0.01em',
            lineHeight: 1.1,
            color: '#fff',
            fontSize: 'clamp(2.2rem, 7vw, 6.5rem)',
          }}
        >
          <GradientLine>The vision</GradientLine>
          <GradientLine>of engineering</GradientLine>
          <span className="flex items-center justify-center gap-3 flex-wrap" style={{ color: '#fff' }}>
            <span style={{ color: '#555' }}>is</span>
            <VideoIcon src={VIDEO_HUMAN} size={110} />
            <span>human</span>
            <span style={{ color: '#555', position: 'relative', top: '0.15em', marginLeft: '0.25em' }}>+</span>
            <VideoIcon src={VIDEO_AI} size={110} />
            <span>AI</span>
          </span>
        </h1>

        <p
          className="mt-4 max-w-xl text-center px-2"
          style={{
            fontSize: 'clamp(0.95rem, 2.2vw, 1.2rem)',
            color: '#888',
            lineHeight: 1.4,
            fontWeight: 400,
          }}
        >
          CONNECT helps teams orchestrate models, tools, memory, and messaging into one operational layer that actually
          ships work.
        </p>

        <button
          type="button"
          className="mt-6 transition-all duration-300 hover:scale-[1.03] hover:shadow-[0px_6px_32px_8px_rgba(39,243,169,0.22)] active:scale-[0.98]"
          style={{
            padding: '12px 28px',
            background: '#000',
            boxShadow: '0px 6px 24px 6px rgba(39, 243, 169, 0.15)',
            borderRadius: 8,
            outline: '1px solid #30463C',
            outlineOffset: -1,
            border: 'none',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
          }}
          onClick={() => {
            window.location.href = '/platform'
          }}
        >
          <span style={{ color: '#fff', fontSize: 14, fontWeight: 400 }}>Join The Movement!</span>
        </button>
      </div>
    </section>
  )
}
