import { Flex } from "@chakra-ui/react";
import Chatbot from "../components/Chatbot";

export default function ReportExpense() {
    return (
        <Flex direction="column" w="full" h={{ base: "calc(100dvh - 120px - env(safe-area-inset-bottom))", md: "calc(100dvh - 60px)" }}>
            <Chatbot />
        </Flex>
    );
}