import { lazy, Suspense } from 'react';
import {HashRouter, Routes, Route, Navigate} from "react-router-dom";
import { Box, Spinner, Center } from '@chakra-ui/react';
import { GoogleOAuthProvider } from '@react-oauth/google';
import Layout from './components/Layout';
import PageErrorBoundary from './components/PageErrorBoundary';
import { isAuthenticated } from './lib/auth';

const Login = lazy(() => import('./pages/login'));
const LoginGoogle = lazy(() => import('./pages/login-google'));
const CreateAccount = lazy(() => import('./pages/create-account'));
const Dashboard = lazy(() => import('./pages/dashboard'));
const ReportExpense = lazy(() => import('./pages/report-expense'));
const TransactionsDisplay = lazy(() => import('./pages/transactions-display'));
const Investments = lazy(() => import('./pages/investments'));
const Budgets = lazy(() => import('./pages/budgets'));
const Account = lazy(() => import('./pages/account'));
const AccountLayout = lazy(() => import('./pages/account-layout'));
const AccountData = lazy(() => import('./pages/account-data'));
const AccountDuplicates = lazy(() => import('./pages/account-duplicates'));
const AccountFamily = lazy(() => import('./pages/account-family'));
const AccountCategories = lazy(() => import('./pages/account-categories'));
const AccountPreferences = lazy(() => import('./pages/account-preferences'));
const AccountMerchants = lazy(() => import('./pages/account-merchants'));
const AccountAssistants = lazy(() => import('./pages/account-assistants'));
const Connect = lazy(() => import('./pages/connect'));

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
        {/* Each page is its own file, downloaded when it is first opened: the first visit loads only what it shows */}
        <PageErrorBoundary>
        <Suspense fallback={<Center minH="60dvh"><Spinner size="xl" /></Center>}>
        <Routes>
          {/* Public Routes */}
          <Route path='/login' element={ <Login/> }/>
          <Route path='/login-google' element={ <LoginGoogle/> }/>
          <Route path='/create-account' element={ <CreateAccount/> }/>
          <Route path='/connect' element={ <Connect/> }/>

          {/* Protected Routes inside Layout */}
          <Route element={<ProtectedRoute><Layout/></ProtectedRoute>}>
            <Route path='/' element={<Dashboard/>}/>
            <Route path='/report-expense' element={<ReportExpense/>}/>
            <Route path='/transactions' element={<TransactionsDisplay/>}/>
            <Route path='/investments' element={<Investments/>}/>
            <Route path='/budgets' element={<Budgets/>}/>
            <Route path='/account' element={<AccountLayout/>}>
              <Route index element={<Account/>}/>
              <Route path='family' element={<AccountFamily/>}/>
              <Route path='categories' element={<AccountCategories/>}/>
              <Route path='merchants' element={<AccountMerchants/>}/>
              <Route path='preferences' element={<AccountPreferences/>}/>
              <Route path='data' element={<AccountData/>}/>
              <Route path='duplicates' element={<AccountDuplicates/>}/>
              <Route path='assistants' element={<AccountAssistants/>}/>
            </Route>
          </Route>
        </Routes>
        </Suspense>
        </PageErrorBoundary>
      </HashRouter>
    </GoogleOAuthProvider>
  );
}

export default App;
