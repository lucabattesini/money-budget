import { Avatar } from "@chakra-ui/react";

// The picture (or initials) of a family member. The name is on hover and for screen readers.
// `person` is one of the family's members ({ id, name, picture }); without one nothing is drawn.
export default function PersonAvatar({ person, size = "xs" }) {
    if (!person) return null;
    return (
        <Avatar.Root size={size} role="img" aria-label={person.name} title={person.name}>
            <Avatar.Fallback name={person.name} />
            {person.picture && <Avatar.Image src={person.picture} alt="" referrerPolicy="no-referrer" />}
        </Avatar.Root>
    );
}
