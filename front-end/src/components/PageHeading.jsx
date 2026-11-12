import { useState } from "react";
import { Heading, HStack, IconButton, Stack, Text } from "@chakra-ui/react";
import { LuInfo } from "react-icons/lu";
import { Tooltip } from "./ui/tooltip";

// A page title with its description: shown under the title on wide screens, and on a phone folded into an (i) icon
// beside the title (tap it to read), so the explanation does not push the content down.
export default function PageHeading({ title, size = "xl", children }) {
    const [open, setOpen] = useState(false);
    return (
        <Stack gap={1}>
            <HStack gap={2}>
                <Heading size={size}>{title}</Heading>
                {children && (
                    <Tooltip
                        content={children}
                        open={open}
                        onOpenChange={(e) => setOpen(e.open)}
                        closeOnClick={false}
                        positioning={{ placement: "bottom-start" }}
                        contentProps={{ maxW: "xs", fontSize: "sm" }}
                    >
                        <IconButton
                            aria-label={`Sobre ${title}`}
                            variant="ghost"
                            size="xs"
                            color="fg.muted"
                            display={{ base: "inline-flex", md: "none" }}
                            onClick={() => setOpen(true)}
                        >
                            <LuInfo />
                        </IconButton>
                    </Tooltip>
                )}
            </HStack>
            {children && (
                <Text color="fg.muted" display={{ base: "none", md: "block" }}>
                    {children}
                </Text>
            )}
        </Stack>
    );
}
