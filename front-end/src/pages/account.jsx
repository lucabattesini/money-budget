import { useState } from "react";
import {
    Center,
    Stack,
    Heading,
    Text,
    Input,
    Button,
    Box,
    Separator,
    Badge,
    Avatar,
    Field,
} from "@chakra-ui/react";
import { FcGoogle } from "react-icons/fc";
import { MdOutlineWhatsapp } from "react-icons/md";

// Mock user — will be replaced with real auth context later
const mockUser = {
    name: "Luca Battesini",
    email: "luca@example.com",
    picture: "",
    whatsappPhone: "",
};

export default function Account() {
    const [whatsappPhone, setWhatsappPhone] = useState(mockUser.whatsappPhone);
    const [saved, setSaved] = useState(false);

    const handleSavePhone = () => {
        // TODO: call PATCH /users/me with whatsapp_phone
        console.log("Saving phone:", whatsappPhone);
        setSaved(true);
        setTimeout(() => setSaved(false), 2500);
    };

    const handleLogout = () => {
        // TODO: clear auth token / session
        console.log("Logging out...");
    };

    return (
        <Center minH="100vh">
            <Stack
                gap={8}
                w="full"
                maxW="sm"
                px={6}
                pt={16}
                pb={12}
            >
                {/* Header */}
                <Stack gap={1}>
                    <Heading size="2xl">My Account</Heading>
                    <Text color="fg.muted">Manage your profile and integrations</Text>
                </Stack>

                {/* Profile card */}
                <Stack
                    gap={4}
                    p={5}
                    borderWidth="1px"
                    borderRadius="xl"
                >
                    <Stack direction="row" align="center" gap={4}>
                        <Avatar.Root size="lg">
                            <Avatar.Fallback name={mockUser.name} />
                        </Avatar.Root>
                        <Stack gap={0}>
                            <Text fontWeight="semibold">{mockUser.name}</Text>
                            <Text fontSize="sm" color="fg.muted">{mockUser.email}</Text>
                        </Stack>
                        <Badge
                            ml="auto"
                            colorPalette="green"
                            variant="subtle"
                            size="sm"
                            gap={1}
                        >
                            <FcGoogle />
                            Google
                        </Badge>
                    </Stack>
                </Stack>

                <Separator />

                {/* WhatsApp integration */}
                <Stack gap={4}>
                    <Stack gap={1}>
                        <Stack direction="row" align="center" gap={2}>
                            <MdOutlineWhatsapp size={20} color="#25D366" />
                            <Heading size="md">WhatsApp Integration</Heading>
                        </Stack>
                        <Text fontSize="sm" color="fg.muted">
                            Link your number to register expenses by sending a message.
                        </Text>
                    </Stack>

                    <Field.Root>
                        <Field.Label>Phone number</Field.Label>
                        <Input
                            id="whatsapp-phone-input"
                            placeholder="+55 51 99999-9999"
                            value={whatsappPhone}
                            onChange={(e) => setWhatsappPhone(e.target.value)}
                        />
                        <Field.HelperText>Include the country code (e.g. +55)</Field.HelperText>
                    </Field.Root>

                    <Button
                        id="save-whatsapp-btn"
                        onClick={handleSavePhone}
                        colorPalette={saved ? "green" : "gray"}
                        variant="outline"
                        w="full"
                    >
                        {saved ? "Saved!" : "Save number"}
                    </Button>
                </Stack>

                <Separator />

                {/* Danger zone */}
                <Stack gap={3}>
                    <Text fontSize="sm" fontWeight="semibold" color="fg.muted">
                        Session
                    </Text>
                    <Button
                        id="logout-btn"
                        onClick={handleLogout}
                        variant="outline"
                        colorPalette="red"
                        w="full"
                    >
                        Sign out
                    </Button>
                </Stack>
            </Stack>
        </Center>
    );
}
