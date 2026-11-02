import { Box, Flex, Heading, Link, Stack, Text } from "@chakra-ui/react";
import { NavLink, Outlet } from "react-router-dom";
import { LuArrowDownUp, LuUser } from "react-icons/lu";

// One entry per section of the account area. Add a line here (and a route in App.jsx) for a new section.
const ACCOUNT_SECTIONS = [
    { name: "Perfil", path: "/account", icon: LuUser, end: true },
    { name: "Importar e exportar", path: "/account/data", icon: LuArrowDownUp },
];

// The account area: a vertical menu on the left and the chosen section on the right.
export default function AccountLayout() {
    return (
        <Flex direction={{ base: "column", md: "row" }} gap={{ base: 4, md: 10 }} maxW="5xl" mx="auto" px={6} pt={12} pb={12}>
            <Stack as="nav" aria-label="Menu da conta" gap={1} flexShrink={0} width={{ base: "full", md: "220px" }}>
                <Heading size="md" mb={2}>Conta</Heading>
                {ACCOUNT_SECTIONS.map((section) => (
                    <Link
                        key={section.path}
                        as={NavLink}
                        to={section.path}
                        end={section.end}
                        display="flex"
                        alignItems="center"
                        gap={3}
                        px={3}
                        py={2}
                        borderRadius="md"
                        color="fg.muted"
                        _hover={{ textDecoration: "none", bg: "bg.muted" }}
                        _currentPage={{ bg: "bg.muted", color: "fg", fontWeight: "semibold" }}
                    >
                        <section.icon />
                        <Text fontSize="sm">{section.name}</Text>
                    </Link>
                ))}
            </Stack>

            <Box flex="1" minW={0}>
                <Outlet />
            </Box>
        </Flex>
    );
}
