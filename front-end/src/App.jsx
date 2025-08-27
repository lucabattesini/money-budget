import './styles/index.css';
import {BrowserRouter, Routes, Route} from "react-router-dom";
import Home from "./pages/home"
import Login from './pages/login';
import CreateAccount from './pages/create-account';
import Dashboard from './pages/dashboard';
import ReportExpense from './pages/report-expense';
import TransactionsDisplay from './pages/transactions-display';
import Investments from './pages/investments';

function App() {
  return (
    <BrowserRouter>
      <Routes>
          <Route path='/' element={ <Dashboard/> }/>
          <Route path='/report-expense' element={ <ReportExpense/> }/>
          <Route path='/transactions' element={ <TransactionsDisplay/> }/>
          <Route path='/investments' element={ <Investments/> }/>
          <Route path='/login' element={ <Login/> }/>
          <Route path='/create-account' element={ <CreateAccount/> }/>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
