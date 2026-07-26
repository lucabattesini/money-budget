import { Box, Stack, Link, Text, Icon } from "@chakra-ui/react";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { LuLayoutDashboard, LuReceipt, LuArrowRightLeft, LuTrendingUp, LuUser } from "react-icons/lu";

export default function Sidebar() {
    const location = useLocation();
    const currentPath = location.pathname;

    const navItems = [
        { name: "Dashboard", path: "/", icon: LuLayoutDashboard },
        { name: "Transações", path: "/transactions", icon: LuArrowRightLeft },
        { name: "Registrar Despesa", path: "/report-expense", icon: LuReceipt },
        { name: "Conta", path: "/account", icon: LuUser },
    ];

    return (
        <Box
            w="250px"
            h="100vh"
            bg="gray.900"
            color="white"
            p={5}
            boxShadow="lg"
            display="flex"
            flexDirection="column"
        >
            <Box mb={10} mt={4}>
                <Text fontSize="2xl" fontWeight="bold" textAlign="center" color="white">
                    Money Budget
                </Text>
            </Box>

            <Stack gap={4} flex="1">
                {navItems.map((item) => {
                    const isActive = currentPath === item.path;
                    return (
                        <Link
                            key={item.name}
                            as={RouterLink}
                            to={item.path}
                            _hover={{ textDecoration: "none", bg: "gray.700" }}
                            bg={isActive ? "white" : "transparent"}
                            color={isActive ? "black" : "gray.300"}
                            p={3}
                            borderRadius="md"
                            display="flex"
                            alignItems="center"
                            gap={3}
                            transition="all 0.2s"
                        >
                            <Icon as={item.icon} boxSize={5} />
                            <Text fontSize="md" fontWeight={isActive ? "bold" : "medium"}>
                                {item.name}
                            </Text>
                        </Link>
                    );
                })}
            </Stack>
        </Box>
    );
}
