import { Tabs, Link } from "@chakra-ui/react";
import Dashboard from "./dashboard";
import ReportExpense from "./report-expense";
import TransactionsDisplay from "./transactions-display";
import Investments from "./investments";

export default function Home() {
    return (
      <Tabs.Root defaultValue={"dashboard"}>
        <Tabs.List>
            <Tabs.Trigger value="dashboard" asChild>
              <Link unstyled href="#dashboard">
                Dashboard
              </Link>
            </Tabs.Trigger>
            <Tabs.Trigger value="report-expense" asChild>
              <Link unstyled href="#report-expense">
                Report Expense
              </Link>
            </Tabs.Trigger>
            <Tabs.Trigger value="transactions-list" asChild>
              <Link unstyled href="#transactions-list">
                Transactions
              </Link>
            </Tabs.Trigger>
            <Tabs.Trigger value="investments" asChild>
              <Link unstyled href="#investments">
                Investments
              </Link>
            </Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="dashboard"> <Dashboard/></Tabs.Content>
        <Tabs.Content value="report-expense"> <ReportExpense/> </Tabs.Content>
        <Tabs.Content value="transactions-list"> <TransactionsDisplay/> </Tabs.Content>
        <Tabs.Content value="investments"> <Investments/> </Tabs.Content>
      </Tabs.Root>  
    );
}