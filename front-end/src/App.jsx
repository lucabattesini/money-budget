import './styles/index.css';
import {HashRouter, Routes, Route, Navigate} from "react-router-dom";
import { Box } from '@chakra-ui/react';
import { GoogleOAuthProvider } from '@react-oauth/google';
import Home from "./pages/home"
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
        <Box position="absolute" right={6} top={6}>
          <Home/>
        </Box>
        <Routes>
          {/* Public Routes */}
          <Route path='/login' element={ <Login/> }/>
          <Route path='/login-google' element={ <LoginGoogle/> }/>
          <Route path='/create-account' element={ <CreateAccount/> }/>

          {/* Protected Routes */}
          <Route path='/' element={ <ProtectedRoute><Dashboard/></ProtectedRoute> }/>
          <Route path='/report-expense' element={ <ProtectedRoute><ReportExpense/></ProtectedRoute> }/>
          <Route path='/transactions' element={ <ProtectedRoute><TransactionsDisplay/></ProtectedRoute> }/>
          <Route path='/investments' element={ <ProtectedRoute><Investments/></ProtectedRoute> }/>
          <Route path='/account' element={ <ProtectedRoute><Account/></ProtectedRoute> }/>
        </Routes>
      </HashRouter>
    </GoogleOAuthProvider>
  );
}

export default App;
