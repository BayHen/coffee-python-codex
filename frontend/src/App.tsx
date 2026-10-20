import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AppLayout } from "./components/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ProductsPage } from "./pages/ProductsPage";
import { OrdersPage } from "./pages/OrdersPage";
import { InventoryPage } from "./pages/InventoryPage";
import { AssistantPage } from "./pages/AssistantPage";

function Protected() {
  const { user } = useAuth();
  const location = useLocation();
  return user ? <AppLayout /> : <Navigate to="/login" state={{ from: location.pathname }} replace />;
}

function ManagementOnly() {
  const { canManage } = useAuth();
  return canManage ? <AssistantPage /> : <Navigate to="/" replace />;
}

export function App() {
  return <AuthProvider><BrowserRouter><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<Protected />}>
      <Route index element={<DashboardPage />} />
      <Route path="products" element={<ProductsPage />} />
      <Route path="menu" element={<Navigate to="/products" replace />} />
      <Route path="pos" element={<Navigate to="/orders" replace />} />
      <Route path="orders" element={<OrdersPage />} />
      <Route path="inventory" element={<InventoryPage />} />
      <Route path="assistant" element={<ManagementOnly />} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></BrowserRouter></AuthProvider>;
}
