import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { Coffee, LockKey, SignIn } from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../lib/api";
import { Button, Input } from "../components/ui";

export function LoginPage() {
  const { user, login, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState("");
  if (user) return <Navigate to="/" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await login(String(form.get("email")), String(form.get("password")));
      navigate((location.state as { from?: string } | null)?.from ?? "/", { replace: true });
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Không thể kết nối máy chủ");
    }
  }

  return <main className="grid min-h-[100dvh] lg:grid-cols-[1.05fr_.95fr]">
    <section className="hidden bg-coffee-dark p-12 text-white lg:flex lg:flex-col lg:justify-between">
      <div className="flex items-center gap-3 text-lg font-bold"><span className="grid size-11 place-items-center rounded-xl bg-white/12"><Coffee size={24} weight="fill" /></span> Smart Coffee Shop</div>
      <div className="max-w-xl"><p className="mb-4 text-sm font-bold uppercase tracking-[.16em] text-orange-200">Một ca làm việc rõ ràng</p><h1 className="font-serif text-6xl leading-[.96] tracking-[-.05em]">Từ quầy gọi món đến kho nguyên liệu.</h1><p className="mt-6 max-w-md text-lg leading-relaxed text-orange-100/80">Theo dõi menu, đơn hàng và tồn kho trong một bảng điều hành tập trung.</p></div>
      <p className="text-sm text-orange-100/55">Dữ liệu và quyền truy cập được xác thực bởi FastAPI.</p>
    </section>
    <section className="flex items-center justify-center p-5 sm:p-10">
      <form onSubmit={submit} className="w-full max-w-md" aria-label="Đăng nhập">
        <div className="mb-8 grid size-14 place-items-center rounded-2xl bg-coffee text-white lg:hidden"><Coffee size={28} weight="fill" /></div>
        <div className="mb-8"><p className="mb-2 text-sm font-bold text-coffee">SMART COFFEE SHOP</p><h1 className="font-serif text-4xl tracking-tight">Đăng nhập</h1><p className="mt-3 text-stone-600">Sử dụng tài khoản nhân viên đã được cấp quyền.</p></div>
        <label className="label" htmlFor="email">Email</label><Input id="email" name="email" type="email" autoComplete="username" required placeholder="ban@coffeeshop.vn" />
        <label className="label mt-5" htmlFor="password">Mật khẩu</label><Input id="password" name="password" type="password" autoComplete="current-password" required />
        {error && <div role="alert" className="mt-4 flex gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700"><LockKey className="shrink-0" size={19} />{error}</div>}
        <Button className="btn-primary mt-6 w-full" type="submit" disabled={loading}><SignIn size={19} />{loading ? "Đang xác thực..." : "Vào bảng điều hành"}</Button>
      </form>
    </section>
  </main>;
}
