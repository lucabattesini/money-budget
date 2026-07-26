import { Flex, Box } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";
import Header from "./Header";

export default function Layout() {
    return (
        <Flex direction="column" h="100vh" w="100vw" overflow="hidden">
            <Header />
            <Box flex="1" overflowY="auto">
                <Outlet />
            </Box>
        </Flex>
    );
}
