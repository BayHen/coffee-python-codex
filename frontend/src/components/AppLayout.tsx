import { useState } from "react";
import { NavLink, Outlet } from "react-router";
import { Archive, Coffee, House, List, Package, Receipt, Robot, SignOut, X } from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { Button } from "./ui";

const nav: Array<{ to: string; label: string; icon: typeof House; end?: boolean; management?: boolean }> = [
  { to: "/", label: "Tổng quan", icon: House, end: true },
  { to: "/products", label: "Sản phẩm", icon: Package },
  { to: "/pos", label: "Bán hàng", icon: Coffee },
  { to: "/orders", label: "Đơn hàng", icon: Receipt },
  { to: "/inventory", label: "Kho", icon: Archive },
  { to: "/assistant", label: "Trợ lý AI", icon: Robot, management: true },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  return <div className="min-h-[100dvh] bg-cream lg:grid lg:grid-cols-[16rem_1fr]">
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-stone-200 bg-cream/95 px-4 backdrop-blur lg:hidden"><strong className="flex items-center gap-2"><Coffee className="text-coffee" weight="fill" /> Smart Coffee</strong><Button aria-label="Mở điều hướng" onClick={() => setOpen(true)}><List size={22} /></Button></header>
    {open && <button aria-label="Đóng điều hướng" className="fixed inset-0 z-30 bg-black/35 lg:hidden" onClick={() => setOpen(false)} />}
    <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-[#29231f] p-4 text-stone-100 transition-transform lg:sticky lg:top-0 lg:h-[100dvh] ${open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}>
      <div className="mb-8 flex items-center justify-between px-2 py-2"><div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-coffee text-white"><Coffee size={22} weight="fill" /></span><div><strong className="block">Smart Coffee</strong><span className="text-xs text-stone-400">Operations</span></div></div><button className="lg:hidden" onClick={() => setOpen(false)} aria-label="Đóng"><X size={22} /></button></div>
      <nav className="space-y-1">{nav.filter((item) => !item.management || user?.role === "Admin" || user?.role === "Manager").map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 font-semibold ${isActive ? "bg-white text-ink" : "text-stone-300 hover:bg-white/8 hover:text-white"}`}><Icon size={20} />{label}</NavLink>)}</nav>
      <div className="mt-auto border-t border-white/10 pt-4"><div className="mb-3 px-2"><strong className="block truncate text-sm">{user?.email}</strong><span className="text-xs text-stone-400">{user?.role}</span></div><button onClick={() => void logout()} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm text-stone-300 hover:bg-white/8 hover:text-white"><SignOut size={19} />Đăng xuất</button></div>
    </aside>
    <main className="min-w-0 p-4 sm:p-6 lg:p-8 xl:p-10"><div className="mx-auto max-w-[1440px]"><Outlet /></div></main>
  </div>;
}
