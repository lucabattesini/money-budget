import './styles/index.css';
import {HashRouter, Routes, Route} from "react-router-dom";
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

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '';

function App() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <HashRouter>
        <Box position="absolute" right={6} top={6}>
          <Home/>
        </Box>
        <Routes>
          <Route path='/' element={ <Dashboard/> }/>
          <Route path='/report-expense' element={ <ReportExpense/> }/>
          <Route path='/transactions' element={ <TransactionsDisplay/> }/>
          <Route path='/investments' element={ <Investments/> }/>
          <Route path='/login' element={ <Login/> }/>
          <Route path='/login-google' element={ <LoginGoogle/> }/>
          <Route path='/create-account' element={ <CreateAccount/> }/>
          <Route path='/account' element={ <Account/> }/>
        </Routes>
      </HashRouter>
    </GoogleOAuthProvider>
  );
}

export default App;
