import './styles/index.css';
import {BrowserRouter, Routes, Route} from "react-router-dom";
import Home from "./pages/home"
import CreateAccount from './pages/create_account';
import BudgetProfile from './pages/create_budget_profile';

function App() {
  return (
    <BrowserRouter>
      <Routes>
          <Route path='/' element={<Home />}/>
          <Route path='budget-profile' element={<BudgetProfile/>}/>
          <Route path='create-account' element={<CreateAccount/>}/>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
