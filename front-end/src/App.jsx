import './styles/index.css';
import {HashRouter, Routes, Route, Navigate} from "react-router-dom";
import { Box } from '@chakra-ui/react';
import { GoogleOAuthProvider } from '@react-oauth/google';
import Layout from './components/Layout';
import Login from './pages/login';
import LoginGoogle from './pages/login-google';
import CreateAccount from './pages/create-account';
import Dashboard from './pages/dashboard';
import ReportExpense from './pages/report-expense';
import TransactionsDisplay from './pages/transactions-display';
import Investments from './pages/investments';
import Account from './pages/account';
import { isAuthenticated } from './lib/auth';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '';

function ProtectedRoute({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login-google" replace />;
  }
  return children;
}

function App() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <HashRouter>
        <Routes>
          {/* Public Routes */}
          <Route path='/login' element={ <Login/> }/>
          <Route path='/login-google' element={ <LoginGoogle/> }/>
          <Route path='/create-account' element={ <CreateAccount/> }/>

          {/* Protected Routes inside Layout */}
          <Route element={<ProtectedRoute><Layout/></ProtectedRoute>}>
            <Route path='/' element={<Dashboard/>}/>
            <Route path='/report-expense' element={<ReportExpense/>}/>
            <Route path='/transactions' element={<TransactionsDisplay/>}/>
            <Route path='/investments' element={<Investments/>}/>
            <Route path='/account' element={<Account/>}/>
          </Route>
        </Routes>
      </HashRouter>
    </GoogleOAuthProvider>
  );
}

export default App;
