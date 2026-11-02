import { Flex } from "@chakra-ui/react";
import Chatbot from "../components/Chatbot";

export default function ReportExpense() {
    return (
        <Flex direction="column" w="full" h="calc(100vh - 60px)">
            <Chatbot />
        </Flex>
    );
}