import { Center, Stack, Heading } from "@chakra-ui/react";
import { Toaster } from "../components/ui/toaster";
import ExpenseForm from "../components/ExpenseForm";

export default function ReportExpense() {
    return (
        <Center>
            <Stack
                minHeight="100vh"
                gap={6}
                w="full"
                maxW="md"
                align="center"
                justify="flex-start"
                py={10}
            >    
                <Toaster/>
                
                <Heading size={"2xl"}>
                    Report Expense
                </Heading>
                
                <ExpenseForm />
            </Stack>
        </Center>
    );
}