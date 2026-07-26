import { Flex } from "@chakra-ui/react";
import { Toaster } from "../components/ui/toaster";
import Chatbot from "../components/Chatbot";

export default function ReportExpense() {
    return (
        <Flex direction="column" w="full" h="calc(100vh - 60px)">
            <Toaster/>
            <Chatbot />
        </Flex>
    );
}