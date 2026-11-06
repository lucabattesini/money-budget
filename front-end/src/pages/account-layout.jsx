import { Box, Flex, Heading, Link, Stack, Text } from "@chakra-ui/react";
import { NavLink, Outlet } from "react-router-dom";
import { LuArrowDownUp, LuSettings, LuStore, LuTags, LuUser, LuUsers } from "react-icons/lu";
import { useLocale } from "../lib/locale";

// One entry per section of the account area. Add a line here (and a route in App.jsx) for a new section.
const ACCOUNT_SECTIONS = [
    { name: "Perfil", path: "/account", icon: LuUser, end: true },
    { name: "Família", path: "/account/family", icon: LuUsers },
    { name: "Categorias", path: "/account/categories", icon: LuTags },
    { name: "Estabelecimentos", path: "/account/merchants", icon: LuStore, needsMerchants: true },
    { name: "Preferências", path: "/account/preferences", icon: LuSettings },
    { name: "Importar e exportar", path: "/account/data", icon: LuArrowDownUp },
];

// The account area: a vertical menu on the left and the chosen section on the right.
export default function AccountLayout() {
    const { merchantsEnabled } = useLocale(); // the merchants section only exists while the family has them on
    const sections = ACCOUNT_SECTIONS.filter((section) => !section.needsMerchants || merchantsEnabled);
    return (
        <Flex direction={{ base: "column", md: "row" }} gap={{ base: 4, md: 10 }} maxW="5xl" mx="auto" px={{ base: 4, md: 6 }} pt={{ base: 6, md: 12 }} pb={12}>
            <Stack as="nav" aria-label="Menu da conta" gap={1} flexShrink={0} width={{ base: "full", md: "220px" }}>
                <Heading size="md" mb={2}>Conta</Heading>
                {sections.map((section) => (
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
                        minH="44px"
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
