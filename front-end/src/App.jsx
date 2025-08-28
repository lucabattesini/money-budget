import './styles/index.css';
import { HashRouter, Routes, Route} from "react-router-dom";
import Login from './pages/login';
import CreateAccount from './pages/create-account';
import Dashboard from './pages/dashboard';
import ReportExpense from './pages/report-expense';
import TransactionsDisplay from './pages/transactions-display';
import Investments from './pages/investments';

function App() {
  return (
    <HashRouter>
      <Routes>
          <Route path='/' element={ <Dashboard/> }/>
          <Route path='/report-expense' element={ <ReportExpense/> }/>
          <Route path='/transactions' element={ <TransactionsDisplay/> }/>
          <Route path='/investments' element={ <Investments/> }/>
          <Route path='/login' element={ <Login/> }/>
          <Route path='/create-account' element={ <CreateAccount/> }/>
      </Routes>
    </HashRouter>
  );
}

export default App;
