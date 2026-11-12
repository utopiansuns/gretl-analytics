// Типы для проверки JS в редакторе (jsconfig.json). На работу приложения не влияют.
interface Window {
  App: any;
  pywebview: { api: Record<string, (...args: any[]) => Promise<any>> };
  __selftest: (text: string) => void;
}
declare const App: any;
