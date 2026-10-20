import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { CircleNotch, WarningCircle } from "@phosphor-icons/react";

export function Button({ className = "", children, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`btn ${className}`} {...props}>{children}</button>;
}
export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="field" {...props} />;
}
export function Panel({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`panel ${className}`} {...props} />;
}
export function PageHeader({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <header className="page-header"><div><h1>{title}</h1><p>{description}</p></div>{action}</header>;
}
export function Loading({ label = "Đang tải" }: { label?: string }) {
  return <div className="state"><CircleNotch className="animate-spin" size={24} /><span>{label}</span></div>;
}
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="state text-red-700"><WarningCircle size={24} /><span>{message}</span>{retry && <Button onClick={retry}>Thử lại</Button>}</div>;
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="state text-stone-500">{children}</div>;
}
export function StatusBadge({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{status}</span>;
}
