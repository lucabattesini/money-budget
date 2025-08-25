import { Tabs } from "@chakra-ui/react";
import Dashboard from "./dashboard";
import ReportExpense from "./report-expense";
import TransactionsDisplay from "./transactions-display";

export default function Home() {
    return (
      <Tabs.Root defaultValue={"dashboard"}>
        <Tabs.List>
            <Tabs.Trigger value="dashboard">Dashboard</Tabs.Trigger>
            <Tabs.Trigger value="report-expense">Report Expense</Tabs.Trigger>
            <Tabs.Trigger value="transactions-list">Transactions List</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="dashboard"> <Dashboard/></Tabs.Content>
        <Tabs.Content value="report-expense"> <ReportExpense/> </Tabs.Content>
        <Tabs.Content value="transactions-list"> <TransactionsDisplay/> </Tabs.Content>
      </Tabs.Root>  
    );
}