import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Sanchalak - Government Scheme Assistant',
  description: 'Your digital guide to government schemes and benefits for farmers',
  keywords: 'government schemes, farming, agriculture, benefits, India',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏛️</text></svg>" />
      </head>
      <body className={`${inter.className} min-h-screen bg-gradient-to-br from-green-50 via-green-100 to-blue-50`}>
        <div id="root">
          {children}
        </div>
      </body>
    </html>
  )
}
