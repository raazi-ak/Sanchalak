import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PM-KISAN Chat Assistant",
  description: "Intelligent Conversational Data Collection for Government Schemes",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
