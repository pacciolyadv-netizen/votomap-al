import './globals.css';

export const metadata = {
  title: 'VotoMap - AL',
  description: 'Painel territorial de resultados eleitorais e perfil do eleitorado (dados públicos).',
};

export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
