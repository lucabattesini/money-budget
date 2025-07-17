import './styles/index.css';
import {BrowserRouter, Routes, Route} from "react-router-dom";
import Home from "./pages/home"
import CreateAccount from './pages/create-account';
import BudgetProfile from './pages/create-budget-profile';
import ReportExpense from './pages/report-expense';

function App() {
  return (
    <BrowserRouter>
      <Routes>
          <Route path='/' element={<Home />}/>
          <Route path='budget-profile' element={<BudgetProfile/>}/>
          <Route path='create-account' element={<CreateAccount/>}/>
          <Route path='report-expense' element={<ReportExpense/>}/>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
